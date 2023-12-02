import cv2
import streamlink
import configparser
from imageRecognize import isSimilarToTargetTemplate
from textRecognize import recognizeTheImage
import math
from pygrabber.dshow_graph import FilterGraph
from win11toast import toast
import threading
import queue
import sys

currentStageCount = 0
currentRefresh = 0
targetStageCount = 7
maxRefresh = 15
globalMainWindowObj = ""
thresholdFor321 = 0.03
thresholdForCourseClear = 0.1
coursesList = set()


def loggingStreaming(mainWindowObj):
    global globalMainWindowObj
    globalMainWindowObj = mainWindowObj
    config = configparser.ConfigParser()
    config.read(r'config.ini', encoding="utf8")

    global currentStageCount
    global currentRefresh
    global targetStageCount
    global maxRefresh
    isDebugWithCompareFrame = config.get(
        'DisplayConfig', 'debugWithCompareFrame') == "True"
    targetStageCount = int(config.get('321Config', 'targetStageCount'))
    maxRefresh = int(config.get('321Config', 'maxRefresh'))
    isStreamWithFullScreen = config.get(
        'StreamSettings', 'isStreamWithFullScreen') == "True"
    mainWindowObj.setTextToLabel(buildDisplayString())

    matchCourseClearTimes = 0
    cooldownTimeForCourseClear = 0
    isMatchForCourseClearCoolDownNow = False
    cooldownTimeFor321 = 0
    isMatchFor321CoolDownNow = False

    streamSource = config.get('StreamSettings', 'streamSource')
    fps = 0
    if streamSource == "LocalVideo":
        cap = cv2.VideoCapture("testImgs/321TestVideo.mkv")
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        cap.set(cv2.CAP_PROP_POS_FRAMES, 285*fps)
        # 260 for test course clear
        # 285 for refresh
    elif streamSource == "Twitch":
        session = streamlink.Streamlink()
        session.set_option("twitch-low-latency", True)
        session.set_option("hls-live-edge", 1)
        session.set_option("hls-segment-stream-data", True)
        session.set_option("hls-playlist-reload-time", "live-edge")
        session.set_option("stream-segment-threads", 2)
        session.set_option("player", "mpv")

        twitchStreamLink = 'https://www.twitch.tv/' + \
            config.get('StreamSettings', 'twtichStreamerName')
        streams = streamlink.streams(twitchStreamLink)
        url = streams['720p60'].url if "720p60" in streams else streams['480p']
        cap = cv2.VideoCapture(url)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
    elif streamSource == "LocalVirtualCamera":
        graph = FilterGraph()
        device = graph.get_input_devices().index("OBS Virtual Camera")
        cap = cv2.VideoCapture(device)
        print("Current Virtual Camera Size - width : " +
              str(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))) + " height : " + str(int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        print("Reszie Virtual Camera to - width : " +
              str(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))) + " height : " + str(int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        fps = 30
        cap.set(cv2.CAP_PROP_POS_FRAMES, 260*fps)
        ret, checkingSource = cap.read()
        obsSourceCheckingResult = cv2.matchTemplate(cv2.convertScaleAbs(cv2.imread(
            "./imgs/obsNoSource.png")), checkingSource, cv2.TM_SQDIFF_NORMED)
        minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(obsSourceCheckingResult)
        if minVal <= 0.01:
            print("Error : OBS Virtual Camera not opened or cloud not be found.")
            toast(
                "Obs Virtual Camera 未開啟",
                "影像來源設定為使用 Obs Virtual Camera，但未正確讀取到畫面。(Obs回傳為待機影像)")
            return

    print("fps : " + str(fps))

    save_interval = 1.5  # before 0.3 when use 321 icon
    frame_count = 0
    val321Queue = queue.Queue()
    while cap.isOpened():
        ret, frame = cap.read()
        frame_count += 1
        if isMatchForCourseClearCoolDownNow:
            cooldownTimeForCourseClear += 1
            if cooldownTimeForCourseClear >= fps*2:
                cooldownTimeForCourseClear = 0
                isMatchForCourseClearCoolDownNow = False

        if isMatchFor321CoolDownNow:
            cooldownTimeFor321 += 1
            if cooldownTimeFor321 >= fps*2:
                cooldownTimeFor321 = 0
                isMatchFor321CoolDownNow = False

        if config.get('DisplayConfig', 'debugWithShowFrame') == "True":
            cv2.imshow('frame', frame)  # may spend about 0.12s to display

        # Compare Per 0.5 seconds
        if math.floor(frame_count % (fps * save_interval)) == 0:
            # Compare with 321 template
            isInputMatchTo321Template = False
            isInputMatchToCourseClearTemplate = False
            global thresholdFor321
            global thresholdForCourseClear
            if not isMatchFor321CoolDownNow:
                threadFor321Detect = threading.Thread(target=lambda q, arg1, arg2, arg3: q.put(isSimilarToTargetTemplate(
                    arg1, arg2, arg3)), args=(val321Queue, "321Mapping", cv2.convertScaleAbs(frame), thresholdFor321))  # 2 count then plus 1)
                threadFor321Detect.start()
            if not isMatchForCourseClearCoolDownNow:
                isInputMatchToCourseClearTemplate = target = isSimilarToTargetTemplate(
                    "courseClearMapping", cv2.convertScaleAbs(frame), thresholdForCourseClear)
            if not isMatchFor321CoolDownNow:
                threadFor321Detect.join()
            # compare with courseClear, cd for 5 seconds
            if isInputMatchToCourseClearTemplate:
                matchCourseClearTimes += 1
                if matchCourseClearTimes >= 1:
                    currentStageCount += 1
                    isMatchForCourseClearCoolDownNow = True
                    mainWindowObj.setTextToLabel(buildDisplayString())
            if not isMatchFor321CoolDownNow:
                isInputMatchTo321Template = val321Queue.get()
            if isInputMatchTo321Template:
                textRecognized = recognizeTheImage(
                    frame, isStreamWithFullScreen, isDebugWithCompareFrame)
                if textRecognized != "" and textRecognized != None:
                    coursesList.add(textRecognized)
                    print("Today Courses : " + str(coursesList))
                    currentRefresh = max(
                        len(coursesList) - currentStageCount - 1, 0)
                    isMatchFor321CoolDownNow = True
                    mainWindowObj.setTextToLabel(buildDisplayString())
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    print("Error : Source is terminated, please check again then restart the program.")
    toast(
        "影像來源已中斷",
        "本來使用的影像來源已中斷，請重新確認後再運行程式")


def buildDisplayString():
    global currentRefresh
    global maxRefresh
    global currentStageCount
    global targetStageCount
    return str(currentRefresh)+" / " + str(maxRefresh) + " 刷  " + \
        str(currentStageCount) + " / " + str(targetStageCount) + " 關"


def addFakeStage():
    global coursesList
    global currentRefresh
    targetCount = currentRefresh + currentStageCount + 1
    i = 0
    while len(coursesList) < targetCount:
        fakeName = "fake stage"+str(i)
        while fakeName in coursesList:
            i += 1
            fakeName = "fake stage"+str(i)
        coursesList.add(fakeName)


def operateOnCurrentRefreshCount(val):
    global currentRefresh
    currentRefresh += val
    global globalMainWindowObj
    global coursesList
    if currentRefresh < 0:
        currentRefresh = 0
        return
    if val < 0:
        val *= -1
        while (val > 0 and len(coursesList) > 0):
            coursesList.pop()
            val -= 1
    else:
        addFakeStage()
    globalMainWindowObj.setTextToLabel(buildDisplayString())


def operateOnCurrentStageCount(val):
    global currentStageCount
    currentStageCount += val
    if currentStageCount < 0:
        currentStageCount = 0
        return
    global globalMainWindowObj
    globalMainWindowObj.setTextToLabel(buildDisplayString())


def exitTheProgram():
    sys.exit("Program shut down noramlly by clicked the exitbtn.")


def resetCurrentValues():
    global currentStageCount
    global currentRefresh
    global coursesList
    currentRefresh = 0
    currentStageCount = 0
    coursesList = set()

    global maxRefresh
    global targetStageCount
    config = configparser.ConfigParser()
    config.read(r'config.ini', encoding="utf8")
    targetStageCount = int(config.get('321Config', 'targetStageCount'))
    maxRefresh = int(config.get('321Config', 'maxRefresh'))

    global globalMainWindowObj
    globalMainWindowObj.setTextToLabel(buildDisplayString())
