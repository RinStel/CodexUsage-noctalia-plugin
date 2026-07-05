import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Widgets

ColumnLayout {
    id: root

    property var pluginApi: null
    property bool saveReady: false
    property var defaults:
        pluginApi && pluginApi.manifest && pluginApi.manifest.metadata
            ? pluginApi.manifest.metadata.defaultSettings || ({})
            : ({})
    property var settings:
        pluginApi && pluginApi.pluginSettings ? pluginApi.pluginSettings : ({})

    property real editBackgroundOpacity: numberSetting("backgroundOpacity", 0.78)
    property real editCardOpacity: numberSetting("cardOpacity", 0.56)
    property int editRefreshIntervalSeconds: boundedIntSetting("refreshIntervalSeconds", 120, 30, 86400)
    property string editCodexHome: stringSetting("codexHome", "")
    property bool editShowTaskBoard: boolSetting("showTaskBoard", true)
    property bool editShowMessages: boolSetting("showMessages", true)
    property int editTaskWindowDays: boundedIntSetting("taskWindowDays", 1, 1, 30)
    property string editThemeMode: stringSetting("themeMode", "system")
    property string editLanguage: stringSetting("language", "zh")

    spacing: Style.marginL

    function clamp(value, low, high) {
        return Math.max(low, Math.min(high, Number(value)));
    }

    function finiteNumber(value, fallback) {
        var numeric = Number(value);
        return isFinite(numeric) ? numeric : Number(fallback);
    }

    function settingValue(name, fallback) {
        if (settings[name] !== undefined && settings[name] !== null)
            return settings[name];
        if (defaults[name] !== undefined && defaults[name] !== null)
            return defaults[name];
        return fallback;
    }

    function boolSetting(name, fallback) {
        return settingValue(name, fallback);
    }

    function numberSetting(name, fallback) {
        return finiteNumber(settingValue(name, fallback), fallback);
    }

    function stringSetting(name, fallback) {
        return String(settingValue(name, fallback));
    }

    function boundedIntSetting(name, fallback, low, high) {
        return Math.round(clamp(numberSetting(name, fallback), low, high));
    }

    function boundedIntValue(value, fallback, low, high) {
        return Math.round(clamp(finiteNumber(value, fallback), low, high));
    }

    function scheduleSave() {
        if (root.saveReady)
            saveTimer.restart();
    }

    function saveSettings() {
        if (!pluginApi || !pluginApi.pluginSettings)
            return;

        pluginApi.pluginSettings.backgroundOpacity = root.editBackgroundOpacity;
        pluginApi.pluginSettings.cardOpacity = root.editCardOpacity;
        pluginApi.pluginSettings.refreshIntervalSeconds = root.editRefreshIntervalSeconds;
        pluginApi.pluginSettings.codexHome = root.editCodexHome;
        pluginApi.pluginSettings.showTaskBoard = root.editShowTaskBoard;
        pluginApi.pluginSettings.showMessages = root.editShowMessages;
        pluginApi.pluginSettings.taskWindowDays = root.editTaskWindowDays;
        pluginApi.pluginSettings.themeMode = root.editThemeMode;
        pluginApi.pluginSettings.language = root.editLanguage;
        pluginApi.saveSettings();
    }

    onEditBackgroundOpacityChanged: scheduleSave()
    onEditCardOpacityChanged: scheduleSave()
    onEditRefreshIntervalSecondsChanged: scheduleSave()
    onEditCodexHomeChanged: scheduleSave()
    onEditShowTaskBoardChanged: scheduleSave()
    onEditShowMessagesChanged: scheduleSave()
    onEditTaskWindowDaysChanged: scheduleSave()
    onEditThemeModeChanged: scheduleSave()
    onEditLanguageChanged: scheduleSave()

    Component.onCompleted: saveReady = true

    Timer {
        id: saveTimer
        interval: 180
        repeat: false
        onTriggered: root.saveSettings()
    }

    NComboBox {
        Layout.fillWidth: true
        label: "外观模式"
        description: "自动跟随系统、浅色或深色。"
        model: [
            { "key": "system", "name": "自动" },
            { "key": "light", "name": "浅色" },
            { "key": "dark", "name": "深色" }
        ]
        currentKey: root.editThemeMode
        onSelected: key => root.editThemeMode = key
    }

    NComboBox {
        Layout.fillWidth: true
        label: "界面语言"
        description: "中文或英文。"
        model: [
            { "key": "zh", "name": "中文" },
            { "key": "en", "name": "English" }
        ]
        currentKey: root.editLanguage
        onSelected: key => root.editLanguage = key
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.marginXXS

        NLabel {
            label: "背景透明度"
            description: "控制桌面小组件整体背景的透明程度。"
        }

        NValueSlider {
            Layout.fillWidth: true
            from: 0.0
            to: 1.0
            stepSize: 0.02
            text: root.editBackgroundOpacity.toFixed(2)
            value: root.editBackgroundOpacity
            onMoved: value => root.editBackgroundOpacity = value
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.marginXXS

        NLabel {
            label: "卡片透明度"
            description: "控制内部卡片背景透明度。"
        }

        NValueSlider {
            Layout.fillWidth: true
            from: 0.0
            to: 1.0
            stepSize: 0.02
            text: root.editCardOpacity.toFixed(2)
            value: root.editCardOpacity
            onMoved: value => root.editCardOpacity = value
        }
    }

    NTextInput {
        label: "刷新间隔"
        description: "单位为秒，最小有效值为 30。"
        placeholderText: "120"
        text: String(root.editRefreshIntervalSeconds)
        onTextChanged: root.editRefreshIntervalSeconds = root.boundedIntValue(parseInt(text || "120"), 120, 30, 86400)
    }

    NTextInput {
        label: "Codex 数据目录"
        description: "留空时读取 ~/.codex。"
        placeholderText: "~/.codex"
        text: root.editCodexHome
        onTextChanged: root.editCodexHome = text
    }

    NComboBox {
        Layout.fillWidth: true
        label: "任务看板时间窗口"
        description: "读取最近多少天的 Codex 任务。"
        model: [
            { "key": "1", "name": "今天" },
            { "key": "3", "name": "近 3 天" },
            { "key": "7", "name": "近 7 天" },
            { "key": "14", "name": "近 14 天" },
            { "key": "30", "name": "近 30 天" }
        ]
        currentKey: String(root.editTaskWindowDays)
        onSelected: key => root.editTaskWindowDays = root.boundedIntValue(parseInt(key), 1, 1, 30)
    }

    NToggle {
        label: "显示任务看板"
        description: "关闭后只显示额度与 token 概览。"
        checked: root.editShowTaskBoard
        onToggled: checked => root.editShowTaskBoard = checked
    }

    NToggle {
        label: "显示运行提示"
        description: "控制 app-server 超时、数据读取提示等消息条。"
        checked: root.editShowMessages
        onToggled: checked => root.editShowMessages = checked
    }
}
