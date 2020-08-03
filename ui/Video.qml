import QtQuick 2.4
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.4
import org.kde.kirigami 2.4 as Kirigami
import Mycroft 1.0 as Mycroft

Mycroft.Delegate {
    id: root
    skillBackgroundSource: sessionData.videoThumbnail

    Mycroft.VideoPlayer {
        id: player
        anchors.fill: parent
        source: sessionData.videoSource //Set URL of video file
        nextAction: "avmusic.next"      //Event to drive next button action in skill
        previousAction: "avmusic.prev"  //Event to drive previous button action in skill
        status: sessionData.status      //Current status of playing video
    }

}