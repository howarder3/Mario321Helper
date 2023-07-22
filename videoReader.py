import cv2
from imageRecognize import isSimilarToTargetTemplate
currentStageCount = 0
currentRefresh = 0
targetStageCount = 7
maxRefresh = 15


def loggingStreaming(mainWindowObj):
    global currentStageCount
    global currentRefresh
    global targetStageCount
    global maxRefresh

    matchCourseClearTimes = 0
    match321Times = 0
    cooldownTimeForCourseClear = 0
    isMatchForCourseClearCoolDownNow = False

    cap = cv2.VideoCapture("testImgs/321TestVideo.mkv")
    cap.set(cv2.CAP_PROP_POS_FRAMES, 260*60)
    # 260 for test course clear
    # 285 for refresh
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    save_interval = 0.4
    frame_count = 0

    while cap.isOpened:
        ret, frame = cap.read()
        frame_count += 1
        if isMatchForCourseClearCoolDownNow:
            cooldownTimeForCourseClear += 1
            if cooldownTimeForCourseClear >= fps*5:
                cooldownTimeForCourseClear = 0
                isMatchForCourseClearCoolDownNow = False
        # cv2.imshow('frame', frame)

        # Compare Per 0.5 seconds
        if frame_count % (fps * save_interval) == 0:
            # Compare with 321 template
            inputMatchTo321Template = isSimilarToTargetTemplate(
                "./sampleImgs/321Mapping.png", cv2.convertScaleAbs(frame), 0.55)  # 2 count then plus 1
            if inputMatchTo321Template:
                match321Times += 1
                if match321Times >= 2:
                    currentRefresh += 1
                    mainWindowObj.setTextToLabel(buildDisplayString())
                    match321Times = 0
            else:
                match321Times = 0
            # compare with courseClear, cd for 5 seconds
            if isSimilarToTargetTemplate("./sampleImgs/courseClearMapping.png", cv2.convertScaleAbs(frame), 0.1):
                if not isMatchForCourseClearCoolDownNow:
                    matchCourseClearTimes += 1
                    if matchCourseClearTimes >= 2:
                        currentStageCount += 1
                        isMatchForCourseClearCoolDownNow = True
                        mainWindowObj.setTextToLabel(buildDisplayString())

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # cap.release()
    # cv2.destroyAllWindows()


def buildDisplayString():
    global currentRefresh
    global maxRefresh
    global currentStageCount
    global targetStageCount
    return str(currentRefresh)+" / " + str(maxRefresh) + " 刷  " + \
        str(currentStageCount) + " / " + str(targetStageCount) + " 關"
