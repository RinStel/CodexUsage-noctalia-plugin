pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Modules.DesktopWidgets
import qs.Services.System
import qs.Widgets

DraggableDesktopWidget {
    id: root

    showBackground: false

    property var pluginApi: null
    property var snapshot: ({ "messages": ["正在读取 codexU 数据"] })
    property bool loading: false
    property string errorText: ""

    readonly property var defaultSettings:
        root.pluginApi && root.pluginApi.manifest && root.pluginApi.manifest.metadata
            ? root.pluginApi.manifest.metadata.defaultSettings || ({})
            : ({})
    readonly property var pluginSettings:
        root.pluginApi && root.pluginApi.pluginSettings ? root.pluginApi.pluginSettings : ({})

    readonly property int refreshIntervalSeconds: intSetting("refreshIntervalSeconds", 120)
    readonly property string configuredCodexHome: stringSetting("codexHome", "")
    readonly property real backgroundOpacity: clamp(numberSetting("backgroundOpacity", 0.78), 0, 1)
    readonly property real cardOpacity: clamp(numberSetting("cardOpacity", 0.56), 0, 1)
    readonly property bool showTaskBoard: boolSetting("showTaskBoard", true)
    readonly property bool showMessages: boolSetting("showMessages", true)
    readonly property int taskWindowDays: clamp(intSetting("taskWindowDays", 1), 1, 30)
    readonly property string themeMode: stringSetting("themeMode", "system")
    readonly property string language: stringSetting("language", "zh")
    readonly property bool useChinese: root.language !== "en"
    readonly property var displayLocale: Qt.locale(root.useChinese ? "zh_CN" : "en_US_POSIX")
    readonly property bool useDarkPalette:
        root.themeMode === "dark" ? true :
        root.themeMode === "light" ? false :
        Settings.data.colorSchemes.darkMode
    readonly property color surfaceColor: root.useDarkPalette ? "#111317" : "#f5f7fb"
    readonly property color panelColor: root.useDarkPalette ? "#1a1d24" : "#eef2f8"
    readonly property color cardColor: root.useDarkPalette ? "#171a21" : "#ffffff"
    readonly property color textColor: root.useDarkPalette ? "#f5f7fb" : "#171b24"
    readonly property color mutedTextColor: root.useDarkPalette ? "#a8afbf" : "#626b7f"
    readonly property color outlineColor: root.useDarkPalette ? "#636b7c" : "#b8c1d1"
    readonly property string providerCommand: Qt.resolvedUrl("scripts/codexu-json").toString().replace("file://", "")

    readonly property real baseWidth: 820
    readonly property real baseHeight: root.showTaskBoard ? 800 : 420
    readonly property real effectiveScale: Math.max(widgetScale, Math.min(root.minScaleWidth / root.baseWidth, root.minScaleHeight / root.baseHeight))
    readonly property real ui: effectiveScale
    readonly property real horizontalPadding: dp(16)
    readonly property real topPadding: dp(18)
    readonly property real bottomPadding: dp(14)
    readonly property real gap: dp(12)
    readonly property color brandPrimary: "#2866f7"
    readonly property color brandPrimaryLight: "#7ba0ff"
    readonly property color brandSecondary: "#8b6dff"
    readonly property color brandHighlight: "#daa3fa"
    readonly property color statusInfo: "#0a84ff"
    readonly property color statusWarning: "#ff9f0a"
    readonly property color statusSuccess: "#30d158"
    readonly property color statusDanger: "#ff453a"
    readonly property color statusNeutral: "#98989d"
    readonly property color trackColor: Qt.alpha(root.mutedTextColor, 0.18)
    readonly property var taskColumnModel: root.taskColumns()

    readonly property real minScaleWidth: 520
    readonly property real minScaleHeight: 320

    implicitWidth: Math.round(root.baseWidth * effectiveScale)
    implicitHeight: Math.round(root.baseHeight * effectiveScale)
    width: implicitWidth
    height: implicitHeight

    function dp(value) {
        return Math.max(1, Math.round(value * root.ui))
    }

    function tr(zhText, enText) {
        return root.useChinese ? zhText : enText;
    }

    function boolSetting(name, fallback) {
        if (root.pluginSettings[name] !== undefined)
            return root.pluginSettings[name];
        if (root.defaultSettings[name] !== undefined)
            return root.defaultSettings[name];
        return fallback;
    }

    function stringSetting(name, fallback) {
        if (root.pluginSettings[name] !== undefined && String(root.pluginSettings[name]).length > 0)
            return String(root.pluginSettings[name]);
        if (root.defaultSettings[name] !== undefined && String(root.defaultSettings[name]).length > 0)
            return String(root.defaultSettings[name]);
        return fallback;
    }

    function numberSetting(name, fallback) {
        if (root.pluginSettings[name] !== undefined && root.pluginSettings[name] !== null)
            return Number(root.pluginSettings[name]);
        if (root.defaultSettings[name] !== undefined && root.defaultSettings[name] !== null)
            return Number(root.defaultSettings[name]);
        return fallback;
    }

    function intSetting(name, fallback) {
        return Math.round(numberSetting(name, fallback));
    }

    function clamp(value, low, high) {
        return Math.max(low, Math.min(high, Number(value)));
    }

    function alphaColor(color, alpha) {
        return Qt.alpha(color, clamp(alpha, 0, 1));
    }

    function formatTokens(value) {
        if (value === undefined || value === null)
            return "--";
        if (value >= 1000000000)
            return (value / 1000000000).toFixed(1) + "B";
        if (value >= 1000000)
            return (value / 1000000).toFixed(1) + "M";
        if (value >= 1000)
            return (value / 1000).toFixed(1) + "K";
        return String(value);
    }

    function formatPercent(value) {
        if (value === undefined || value === null)
            return "--";
        return Math.round(value) + "%";
    }

    function formatClock(value) {
        return value ? new Date(value).toLocaleTimeString(root.displayLocale, "HH:mm") : "--";
    }

    function formatResetDateTime(value) {
        if (!value)
            return "--";
        var date = new Date(value);
        var sameDay = date.getFullYear() === new Date().getFullYear()
            && date.getMonth() === new Date().getMonth()
            && date.getDate() === new Date().getDate();
        if (sameDay)
            return date.toLocaleTimeString(root.displayLocale, "HH:mm");
        return root.useChinese
            ? date.toLocaleString(root.displayLocale, "MM月dd日  HH:mm")
            : date.toLocaleString(root.displayLocale, "MM/dd HH:mm");
    }

    function formatUSD(value) {
        if (value === undefined || value === null)
            return "--";
        if (value >= 1000)
            return "$" + Math.round(value).toLocaleString();
        return "$" + Number(value).toFixed(2);
    }

    function localUsage() {
        return snapshot.local || {};
    }

    function detailedUsage() {
        return (localUsage().detailedUsage || {});
    }

    function pricedUsage(key, fallbackTokens) {
        var detailed = detailedUsage();
        if (detailed[key])
            return detailed[key];
        return {
            "estimatedCostUSD": null,
            "tokens": {
                "cachedInputTokens": 0,
                "outputTokens": 0,
                "totalTokens": fallbackTokens,
                "uncachedInputTokens": fallbackTokens
            }
        };
    }

    function lifetimeUsage() {
        var usage = root.pricedUsage("lifetime", root.localUsage().lifetimeTokens);
        if (root.snapshot.cloudLifetimeTokens !== undefined && root.snapshot.cloudLifetimeTokens !== null) {
            usage = JSON.parse(JSON.stringify(usage));
            if (!usage.tokens)
                usage.tokens = {};
            usage.tokens.totalTokens = root.snapshot.cloudLifetimeTokens;
        }
        return usage;
    }

    function taskColumns() {
        if (snapshot.taskBoard && snapshot.taskBoard.columns)
            return snapshot.taskBoard.columns;
        return [
            { "id": "active", "title": root.tr("进行中", "Active"), "count": 0, "items": [] },
            { "id": "pending", "title": root.tr("待处理", "Pending"), "count": 0, "items": [] },
            { "id": "scheduled", "title": root.tr("定时", "Scheduled"), "count": 0, "items": [] },
            { "id": "done", "title": root.tr("完成", "Done"), "count": 0, "items": [] }
        ];
    }

    function localizedTaskColumnTitle(kind, fallbackTitle) {
        if (kind === "active")
            return root.tr("进行中", "Active");
        if (kind === "pending")
            return root.tr("待处理", "Pending");
        if (kind === "scheduled")
            return root.tr("定时", "Scheduled");
        if (kind === "done")
            return root.tr("完成", "Done");
        return fallbackTitle || "";
    }

    function localizedTaskDetail(detail) {
        if (root.useChinese || !detail)
            return detail || "";
        return String(detail)
            .replace("每天", "Daily")
            .replace("每周", "Weekly")
            .replace("每小时", "Hourly");
    }

    function localizedReaderMessage(message) {
        if (root.useChinese || !message)
            return message || "";
        if (message === "正在读取 codexU 数据")
            return "Reading codexU data";
        if (message.indexOf("未找到 codex") >= 0)
            return "Codex executable not found";
        if (message.indexOf("app-server 启动失败") >= 0)
            return "Failed to start app-server";
        if (message.indexOf("app-server 响应超时") >= 0)
            return "app-server response timed out";
        if (message.indexOf("未找到 Codex state_5.sqlite") >= 0)
            return "Codex state_5.sqlite not found";
        if (message.indexOf("SQLite 查询失败") >= 0)
            return "SQLite query failed";
        if (message.indexOf("未找到 Codex session 日志") >= 0)
            return "Codex session logs not found";
        if (message.indexOf("未找到 Codex token_count 事件") >= 0)
            return "Codex token_count events not found";
        if (message.indexOf("任务看板未找到 SQLite 数据源") >= 0)
            return "Task board SQLite data source not found";
        return message.replace("未知错误", "Unknown error");
    }

    function columnAccent(kind) {
        if (kind === "active")
            return root.statusWarning;
        if (kind === "scheduled")
            return root.brandSecondary;
        if (kind === "done")
            return root.statusSuccess;
        return root.statusNeutral;
    }

    function chipAccent(chip, kind) {
        var normalized = String(chip || "").toLowerCase();
        if (normalized === "high" || normalized === "urgent")
            return root.statusDanger;
        if (normalized === "medium" || normalized === "active")
            return root.statusWarning;
        if (normalized === "cron" || normalized === "wake")
            return root.brandSecondary;
        if (normalized === "done")
            return root.statusSuccess;
        return root.columnAccent(kind);
    }

    function woolAccent(value) {
        var cost = Number(value || 0);
        if (cost >= 200)
            return root.brandPrimaryLight;
        if (cost >= 100)
            return root.brandSecondary;
        if (cost >= 20)
            return root.statusInfo;
        return root.statusWarning;
    }

    function woolFraction(cost) {
        var clamped = Math.max(0, Math.min(Number(cost || 0), 46500));
        var ceiling = 200;
        var band = 0.28;
        if (clamped <= ceiling)
            return band * (clamped / ceiling);
        var remaining = Math.max(46500 - ceiling, 1);
        return band + (1 - band) * ((clamped - ceiling) / remaining);
    }

    function chipIcon(chip) {
        var normalized = String(chip || "").toLowerCase();
        if (normalized === "cron" || normalized === "wake")
            return "◔";
        if (normalized === "done")
            return "✓";
        return "▮";
    }

    function relativeTimeText(value) {
        if (!value)
            return "";
        var seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
        if (seconds < 60)
            return root.tr("刚刚", "just now");
        var minutes = Math.floor(seconds / 60);
        if (minutes < 60)
            return root.useChinese ? (minutes + " 分钟前") : (minutes + "m ago");
        var hours = Math.floor(minutes / 60);
        if (hours < 24)
            return root.useChinese ? (hours + " 小时前") : (hours + "h ago");
        var days = Math.floor(hours / 24);
        return root.useChinese ? (days + " 天前") : (days + "d ago");
    }

    function taskAvatarText(item) {
        if (!item)
            return "C";
        if (String(item.code || "").indexOf("AUTO") === 0)
            return "B";
        var detail = String(item.detail || "");
        var source = detail.split("·")[0].trim();
        if (source.length > 0)
            return source[0].toUpperCase();
        return "C";
    }

    function providerCommandParts() {
        var env = [];
        if (configuredCodexHome.length > 0)
            env.push("CODEXU_CODEX_HOME=" + configuredCodexHome);
        if (taskWindowDays > 1)
            env.push("CODEXU_TASK_WINDOW_DAYS=" + String(taskWindowDays));
        if (env.length > 0)
            return ["env"].concat(env).concat([providerCommand]);
        return [providerCommand];
    }

    function refresh() {
        if (provider.running)
            return;
        loading = true;
        errorText = "";
        provider.command = root.providerCommandParts();
        providerStartupGuard.restart();
        provider.running = true;
    }

    Timer {
        interval: Math.max(30, root.refreshIntervalSeconds) * 1000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Process {
        id: provider
        command: root.providerCommandParts()
        running: false

        onRunningChanged: {
            if (running) {
                providerStartupGuard.stop();
                providerWatchdog.restart();
                return;
            }
            providerWatchdog.stop();
            root.loading = false;
        }

        stdout: StdioCollector {
            onStreamFinished: providerWatchdog.stop()
        }

        stderr: StdioCollector {
            onStreamFinished: {
                providerWatchdog.stop();
                if (this.text.length > 0)
                    root.errorText = this.text.trim();
            }
        }

        onExited: function(exitCode) {
            root.loading = false;
            providerStartupGuard.stop();
            providerWatchdog.stop();
            if (stdout.text.length > 0) {
                try {
                    root.snapshot = JSON.parse(stdout.text);
                } catch (error) {
                    root.errorText = root.tr("数据解析失败", "Failed to parse data");
                }
            }
            if (exitCode !== 0 && root.errorText.length === 0)
                root.errorText = root.tr("数据读取失败", "Failed to read data");
        }
    }

    Timer {
        id: providerStartupGuard
        interval: 1500
        repeat: false
        onTriggered: {
            if (root.loading && root.errorText.length === 0) {
                root.loading = false;
                root.errorText = root.tr("数据提供器未能启动，请检查 Noctalia 的 python3 环境。", "Failed to start data provider. Check python3 in the Noctalia environment.");
            }
        }
    }

    Timer {
        id: providerWatchdog
        interval: 45000
        repeat: false
        onTriggered: {
            if (provider.running) {
                provider.running = false;
                root.loading = false;
                if (root.errorText.length === 0)
                    root.errorText = root.tr("数据读取超时", "Data provider timed out");
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: Style.radiusL
        color: root.alphaColor(root.surfaceColor, root.backgroundOpacity)
        border.color: Qt.alpha(root.outlineColor, 0.22)
        border.width: 1
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: root.horizontalPadding
        anchors.rightMargin: root.horizontalPadding
        anchors.topMargin: root.topPadding
        anchors.bottomMargin: root.bottomPadding
        spacing: root.gap

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: dp(34)
            spacing: dp(10)

            Image {
                Layout.preferredWidth: dp(34)
                Layout.preferredHeight: dp(34)
                source: Qt.resolvedUrl("../Resources/codexU-icon.png")
                fillMode: Image.PreserveAspectFit
                smooth: true
                visible: status === Image.Ready
            }

            NText {
                text: root.tr("Codex 用量统计", "Codex Usage")
                color: root.textColor
                font.pointSize: fp(22)
                font.bold: true
                applyUiScale: false
            }

            Pill {
                text: (root.snapshot.account && root.snapshot.account.planType)
                    ? root.snapshot.account.planType.toUpperCase()
                    : "LOCAL"
                light: true
            }

            Item { Layout.fillWidth: true }

            NText {
                text: root.snapshot.refreshedAt ? (root.tr("上次刷新 ", "Last refresh ") + root.formatClock(root.snapshot.refreshedAt)) : ""
                color: root.mutedTextColor
                font.pointSize: fp(Style.fontSizeS)
                font.bold: true
                applyUiScale: false
                Layout.alignment: Qt.AlignVCenter
            }

            IconButton {
                text: "↻"
                spinning: root.loading
                onClicked: root.refresh()
            }
        }

        GlassPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: dp(300)
            Layout.maximumHeight: root.showTaskBoard ? dp(300) : -1

            RowLayout {
                id: overviewRow
                anchors.fill: parent
                anchors.margins: dp(16)
                spacing: dp(26)

                QuotaOverview {
                    Layout.preferredWidth: dp(176)
                    Layout.fillHeight: true
                    primary: root.snapshot.primary
                    secondary: root.snapshot.secondary
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: dp(13)

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: dp(150)
                        spacing: dp(12)

                        UsageMetricCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            title: root.tr("今日", "Today")
                            icon: "☀"
                            accentColor: root.statusInfo
                            usage: root.pricedUsage("today", root.localUsage().todayTokens)
                        }
                        UsageMetricCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            title: root.tr("近 7 天", "Last 7 Days")
                            icon: "▤"
                            accentColor: root.brandSecondary
                            usage: root.pricedUsage("sevenDay", root.localUsage().sevenDayTokens)
                        }
                        UsageMetricCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            title: root.tr("累计", "Lifetime")
                            icon: "Σ"
                            accentColor: root.statusNeutral
                            usage: root.lifetimeUsage()
                        }
                    }

                    WoolCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: dp(96)
                        accentColor: root.statusInfo
                        usage: root.detailedUsage().month
                    }
                }
            }
        }

        GlassPanel {
            visible: root.showMessages && root.errorText.length > 0
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? dp(32) : 0

            NText {
                anchors.fill: parent
                anchors.margins: Style.marginS
                text: root.localizedReaderMessage(root.errorText)
                color: root.mutedTextColor
                font.pointSize: fp(Style.fontSizeS)
                elide: Text.ElideRight
                applyUiScale: false
            }
        }

        GlassPanel {
            visible: root.showTaskBoard
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: dp(240)

            RowLayout {
                anchors.fill: parent
                anchors.margins: dp(12)
                spacing: dp(8)

                Repeater {
                    model: root.taskColumnModel

                    TaskColumn {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        columnData: modelData
                    }
                }
            }
        }
    }

    function fp(value) {
        return Math.max(1, value * root.ui)
    }

    component GlassPanel: Item {
        default property alias content: contentLayer.data

        Rectangle {
            anchors.fill: parent
            radius: Style.radiusM
            color: root.alphaColor(root.panelColor, root.cardOpacity)
            border.color: Qt.alpha(root.outlineColor, 0.18)
            border.width: 1
        }

        Item {
            id: contentLayer
            anchors.fill: parent
            clip: true
        }
    }

    component SoftCard: Item {
        default property alias content: contentLayer.data
        property color accentColor: Color.mOutline

        Rectangle {
            anchors.fill: parent
            radius: Style.radiusM
            color: root.alphaColor(root.cardColor, root.cardOpacity)
            border.color: Qt.alpha(accentColor, 0.28)
            border.width: 1
        }

        Item {
            id: contentLayer
            anchors.fill: parent
            clip: true
        }
    }

    component Pill: Item {
        id: pillRoot
        property string text
        property bool light: false

        Layout.preferredWidth: label.implicitWidth + dp(18)
        Layout.preferredHeight: dp(26)

        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: light ? root.surfaceColor : root.panelColor
            opacity: light ? 0.92 : 0.68
            border.color: Qt.alpha(root.outlineColor, 0.18)
        }

        NText {
            id: label
            anchors.centerIn: parent
            text: pillRoot.text
            color: root.mutedTextColor
            font.pointSize: fp(11)
            font.bold: true
            applyUiScale: false
        }
    }

    component IconButton: Item {
        id: iconButtonRoot
        signal clicked()
        property string text
        property bool spinning: false

        Layout.preferredWidth: dp(36)
        Layout.preferredHeight: dp(36)

        Rectangle {
            anchors.fill: parent
            radius: dp(10)
            color: root.panelColor
            opacity: 0.68
            border.color: Qt.alpha(root.outlineColor, 0.14)
            border.width: 1
        }

        Item {
            id: iconGlyph
            anchors.centerIn: parent
            width: glyphText.implicitWidth
            height: glyphText.implicitHeight

            NText {
                id: glyphText
                anchors.centerIn: parent
                text: iconButtonRoot.text
                color: root.mutedTextColor
                font.pointSize: fp(16)
                font.bold: true
                applyUiScale: false
            }

            RotationAnimation {
                id: spinAnim
                target: iconGlyph
                from: 0
                to: 360
                duration: 900
                loops: Animation.Infinite
                running: iconButtonRoot.spinning
            }
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: iconButtonRoot.clicked()
        }
    }

    component QuotaOverview: Item {
        property var primary
        property var secondary

        ColumnLayout {
            anchors.fill: parent
            spacing: dp(8)

            Item {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: dp(170)
                Layout.preferredHeight: dp(170)
                clip: true

                Canvas {
                    id: ringCanvas
                    anchors.fill: parent
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d");
                        var center = width / 2;
                        var primaryPercent = ((primary && primary.remainingPercent) || 0) / 100;
                        var secondaryPercent = ((secondary && secondary.remainingPercent) || 0) / 100;
                        var outerLine = dp(18);
                        var innerLine = dp(14);
                        var outerRadius = center - outerLine / 2;
                        var innerFrame = dp(122);
                        var innerRadius = Math.max(0, innerFrame / 2 - innerLine / 2);
                        ctx.reset();
                        ctx.lineCap = "butt";

                        ctx.lineWidth = outerLine;
                        ctx.strokeStyle = root.trackColor;
                        ctx.beginPath();
                        ctx.arc(center, center, outerRadius, -Math.PI / 2 + Math.PI * 2 * primaryPercent, Math.PI * 1.5);
                        ctx.stroke();
                        ctx.strokeStyle = root.brandPrimary;
                        ctx.beginPath();
                        ctx.arc(center, center, outerRadius, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * primaryPercent);
                        ctx.stroke();

                        ctx.lineWidth = innerLine;
                        ctx.strokeStyle = root.trackColor;
                        ctx.beginPath();
                        ctx.arc(center, center, innerRadius, -Math.PI / 2 + Math.PI * 2 * secondaryPercent, Math.PI * 1.5);
                        ctx.stroke();
                        ctx.strokeStyle = root.brandSecondary;
                        ctx.beginPath();
                        ctx.arc(center, center, innerRadius, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * secondaryPercent);
                        ctx.stroke();
                    }
                }

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: dp(2)

                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: dp(4)
                        NText { text: "5h"; color: root.brandPrimary; font.pointSize: fp(10); font.bold: true; applyUiScale: false; Layout.alignment: Qt.AlignVCenter }
                        NText { text: root.formatPercent(primary && primary.remainingPercent); color: root.textColor; font.pointSize: fp(15); font.bold: true; applyUiScale: false; Layout.alignment: Qt.AlignVCenter }
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: dp(4)
                        NText { text: "7d"; color: root.brandSecondary; font.pointSize: fp(10); font.bold: true; applyUiScale: false; Layout.alignment: Qt.AlignVCenter }
                        NText { text: root.formatPercent(secondary && secondary.remainingPercent); color: root.textColor; font.pointSize: fp(15); font.bold: true; applyUiScale: false; Layout.alignment: Qt.AlignVCenter }
                    }
                }

                Connections {
                    target: root
                    function onSnapshotChanged() { ringCanvas.requestPaint(); }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                spacing: dp(4)

                LegendLine {
                    colorDot: root.brandPrimary
                    label: root.tr("5h 重置", "5h resets")
                    value: root.formatClock(primary && primary.resetsAt)
                }
                LegendLine {
                    colorDot: root.brandSecondary
                    label: root.tr("7d 重置", "7d resets")
                    value: root.formatResetDateTime(secondary && secondary.resetsAt)
                }
            }
        }

        onPrimaryChanged: ringCanvas.requestPaint()
        onSecondaryChanged: ringCanvas.requestPaint()
    }

    component LegendLine: RowLayout {
        property color colorDot
        property string label
        property string value

        Layout.fillWidth: true
        spacing: dp(8)

        Rectangle {
            Layout.preferredWidth: dp(8)
            Layout.preferredHeight: dp(8)
            radius: width / 2
            color: colorDot
        }
        NText { text: label; color: root.mutedTextColor; font.pointSize: fp(Style.fontSizeS); font.bold: true; applyUiScale: false }
        Item { Layout.fillWidth: true }
        NText { text: value; color: root.textColor; font.pointSize: fp(Style.fontSizeS); font.bold: true; applyUiScale: false }
    }

    component UsageMetricCard: SoftCard {
        property string title
        property string icon
        property var usage

        readonly property var safeTokens: usage && usage.tokens ? usage.tokens : ({})
        readonly property string costText: {
            var usd = usage && usage.estimatedCostUSD;
            return usd === undefined || usd === null ? "--" : root.formatUSD(usd);
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: dp(10)
            spacing: dp(7)

            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: dp(20)

                Rectangle {
                    Layout.preferredWidth: dp(18)
                    Layout.preferredHeight: dp(18)
                    radius: dp(5)
                    color: root.trackColor

                    NText {
                        anchors.centerIn: parent
                        text: icon
                        color: root.mutedTextColor
                        font.pointSize: fp(10)
                        font.bold: true
                        applyUiScale: false
                    }
                }

                NText {
                    text: title
                    color: root.mutedTextColor
                    font.pointSize: fp(11)
                    font.bold: true
                    applyUiScale: false
                }

                Item { Layout.fillWidth: true }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: dp(4)

                NText {
                    text: root.formatTokens(usage && usage.tokens && usage.tokens.totalTokens)
                    color: root.textColor
                    font.pointSize: fp(19)
                    font.bold: true
                    applyUiScale: false
                }
                NText {
                    text: "≈"
                    color: root.mutedTextColor
                    font.pointSize: fp(13)
                    applyUiScale: false
                    Layout.alignment: Qt.AlignVCenter
                }
                NText {
                    text: costText
                    color: root.mutedTextColor
                    font.pointSize: fp(13)
                    applyUiScale: false
                    Layout.alignment: Qt.AlignVCenter
                }
                Item { Layout.fillWidth: true }
            }

            SplitBar {
                Layout.fillWidth: true
                Layout.preferredHeight: dp(8)
                tokens: safeTokens
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: dp(6)

                TokenChip {
                    Layout.fillWidth: true
                    colorDot: root.statusInfo
                    label: root.tr("未缓存", "Input")
                    value: root.formatTokens(safeTokens.uncachedInputTokens)
                }
                TokenChip {
                    Layout.fillWidth: true
                    colorDot: root.brandSecondary
                    label: root.tr("缓存", "Cached")
                    value: root.formatTokens(safeTokens.cachedInputTokens)
                }
                TokenChip {
                    Layout.fillWidth: true
                    colorDot: root.statusWarning
                    label: root.tr("输出", "Output")
                    value: root.formatTokens(safeTokens.outputTokens)
                }
            }
        }
    }

    component TokenChip: ColumnLayout {
        property color colorDot
        property string label
        property string value

        spacing: dp(2)

        RowLayout {
            Layout.fillWidth: true
            spacing: dp(3)

            Rectangle {
                Layout.preferredWidth: dp(6)
                Layout.preferredHeight: dp(6)
                radius: width / 2
                color: colorDot
            }
            NText {
                text: label
                color: root.mutedTextColor
                font.pointSize: fp(8)
                applyUiScale: false
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
        NText {
            Layout.fillWidth: true
            text: value
            color: root.textColor
            font.pointSize: fp(9)
            font.bold: true
            applyUiScale: false
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignLeft
        }
    }

    component SplitBar: Item {
        property var tokens
        property real uncached: Math.max(0, tokens.uncachedInputTokens || 0)
        property real cached: Math.max(0, tokens.cachedInputTokens || 0)
        property real output: Math.max(0, tokens.outputTokens || 0)
        property real total: Math.max(1, uncached + cached + output)

        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: root.trackColor
            opacity: 0.8
        }

        Row {
            anchors.fill: parent
            clip: true

            Rectangle { width: parent.width * uncached / total; height: parent.height; color: root.statusInfo }
            Rectangle { width: parent.width * cached / total; height: parent.height; color: root.brandSecondary }
            Rectangle { width: parent.width * output / total; height: parent.height; color: root.statusWarning }
        }
    }

    component WoolCard: SoftCard {
        id: woolCardRoot
        property var usage
        readonly property real currentCost: Number((usage && usage.estimatedCostUSD) || 0)
        readonly property color currentAccent: root.woolAccent(currentCost)
        readonly property var milestones: [
            { "title": "Plus", "amount": 20, "color": root.statusInfo },
            { "title": "Pro100", "amount": 100, "color": root.brandSecondary },
            { "title": "Pro200", "amount": 200, "color": root.brandPrimaryLight }
        ]

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: dp(10)
            spacing: dp(8)

            RowLayout {
                Layout.fillWidth: true
                NText {
                    text: (currentCost >= 20 ? "↗" : "◎") + "  " + root.tr("羊毛进度", "Value Progress")
                    color: root.textColor
                    font.pointSize: fp(12)
                    font.bold: true
                    applyUiScale: false
                }
                Item { Layout.fillWidth: true }
                NText {
                    text: root.formatUSD(usage && usage.estimatedCostUSD)
                    color: root.textColor
                    font.pointSize: fp(16)
                    font.bold: true
                    applyUiScale: false
                }
                NText {
                    text: "/ $46.5K"
                    color: root.mutedTextColor
                    font.pointSize: fp(10)
                    font.bold: true
                    applyUiScale: false
                }
            }

            Item {
                id: woolBar
                Layout.fillWidth: true
                Layout.preferredHeight: dp(20)

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    height: dp(10)
                    radius: height / 2
                    color: root.trackColor
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    width: currentCost > 0 ? Math.max(dp(5), parent.width * root.woolFraction(currentCost)) : 0
                    height: dp(10)
                    radius: height / 2
                    color: currentAccent
                }

                Repeater {
                    model: woolCardRoot.milestones
                    delegate: Rectangle {
                        required property var modelData
                        anchors.verticalCenter: parent.verticalCenter
                        x: woolBar.width * root.woolFraction(modelData.amount) - width / 2
                        width: dp(7)
                        height: width
                        radius: width / 2
                        color: modelData.color
                        border.color: root.surfaceColor
                        border.width: 1
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: dp(8)
                LegendDot { colorDot: root.statusInfo; text: "Plus" }
                LegendDot { colorDot: root.brandSecondary; text: "Pro100" }
                LegendDot { colorDot: root.brandPrimaryLight; text: "Pro200" }
            }
        }
    }

    component LegendDot: RowLayout {
        id: legendDotRoot
        property color colorDot
        property string text

        spacing: dp(5)

        Rectangle {
            Layout.preferredWidth: dp(8)
            Layout.preferredHeight: dp(8)
            radius: width / 2
            color: colorDot
        }
        NText { text: legendDotRoot.text; color: root.mutedTextColor; font.pointSize: fp(Style.fontSizeXS); font.bold: true; applyUiScale: false }
    }

    component TaskColumn: Item {
        id: taskColumnRoot
        property var columnData: ({ "id": "", "title": "", "count": 0, "items": [] })
        readonly property var safeColumnData: columnData || ({ "id": "", "title": "", "count": 0, "items": [] })
        readonly property color accent: root.columnAccent(safeColumnData.id)
        readonly property var safeItems: safeColumnData.items || []

        Rectangle {
            anchors.fill: parent
            radius: dp(10)
            color: root.alphaColor(accent, 0.065 * root.cardOpacity)
            border.color: Qt.alpha(accent, 0.12)
            border.width: 1
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: dp(12)
            spacing: dp(9)

            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: dp(26)

                Rectangle {
                    Layout.preferredWidth: dp(8)
                    Layout.preferredHeight: dp(8)
                    radius: width / 2
                    color: accent
                }

                NText {
                    text: root.localizedTaskColumnTitle(taskColumnRoot.safeColumnData.id, taskColumnRoot.safeColumnData.title)
                    color: root.textColor
                    font.pointSize: fp(11)
                    font.bold: true
                    applyUiScale: false
                }
                NText {
                    text: String(taskColumnRoot.safeColumnData.count || 0)
                    color: root.mutedTextColor
                    font.pointSize: fp(10)
                    font.bold: true
                    applyUiScale: false
                    Layout.leftMargin: dp(6)
                }
                Item { Layout.fillWidth: true }
            }

            Flickable {
                id: cardsFlick
                visible: taskColumnRoot.safeItems.length > 0
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: width
                contentHeight: cardsCol.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height

                ColumnLayout {
                    id: cardsCol
                    width: cardsFlick.width
                    spacing: dp(9)

                    Repeater {
                        model: taskColumnRoot.safeItems

                        TaskCard {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: implicitHeight
                            item: modelData
                            accent: taskColumnRoot.accent
                        }
                    }

                    NText {
                        visible: (taskColumnRoot.safeColumnData.count || 0) > taskColumnRoot.safeItems.length
                        text: root.useChinese
                            ? ("+ " + ((taskColumnRoot.safeColumnData.count || 0) - taskColumnRoot.safeItems.length) + " 项")
                            : ("+ " + ((taskColumnRoot.safeColumnData.count || 0) - taskColumnRoot.safeItems.length) + " more")
                        color: root.mutedTextColor
                        font.pointSize: fp(Style.fontSizeXS)
                        font.bold: true
                        applyUiScale: false
                        Layout.leftMargin: dp(6)
                    }
                }
            }

            Item {
                visible: taskColumnRoot.safeItems.length === 0
                Layout.fillWidth: true
                Layout.fillHeight: true

                Column {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: dp(5)

                    NText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "◌"
                        color: root.mutedTextColor
                        font.pointSize: fp(13)
                        font.bold: true
                        applyUiScale: false
                    }

                    NText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: root.tr("暂无", "No items")
                        color: root.mutedTextColor
                        font.pointSize: fp(10)
                        font.bold: true
                        applyUiScale: false
                    }
                }
            }
        }
    }

    component TaskCard: Item {
        id: taskCardRoot
        property var item: ({ "code": "", "title": "", "detail": "", "chip": "", "updatedAt": null })
        readonly property var safeItem: item || ({ "code": "", "title": "", "detail": "", "chip": "", "updatedAt": null })
        property color accent
        implicitHeight: contentCol.implicitHeight + dp(22)
        clip: true

        Rectangle {
            anchors.fill: parent
            radius: dp(10)
            color: root.alphaColor(root.cardColor, root.cardOpacity)
            border.color: Qt.alpha(root.textColor, 0.075)
            border.width: 1
        }

        ColumnLayout {
            id: contentCol
            anchors.fill: parent
            anchors.margins: dp(11)
            spacing: dp(6)

            RowLayout {
                Layout.fillWidth: true
                NText {
                    text: taskCardRoot.safeItem.code
                    color: root.mutedTextColor
                    font.pointSize: fp(Style.fontSizeXS)
                    font.bold: true
                    applyUiScale: false
                }
                Item { Layout.fillWidth: true }
                NText {
                    text: root.relativeTimeText(taskCardRoot.safeItem.updatedAt)
                    color: root.mutedTextColor
                    font.pointSize: fp(Style.fontSizeXS)
                    applyUiScale: false
                }
            }

            NText {
                Layout.fillWidth: true
                text: taskCardRoot.safeItem.title
                color: root.textColor
                font.pointSize: fp(Style.fontSizeS)
                font.bold: true
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                applyUiScale: false
            }

            NText {
                Layout.fillWidth: true
                text: root.localizedTaskDetail(taskCardRoot.safeItem.detail)
                color: root.mutedTextColor
                font.pointSize: fp(Style.fontSizeXS)
                elide: Text.ElideRight
                applyUiScale: false
            }

            RowLayout {
                Layout.fillWidth: true

                TaskChip {
                    text: taskCardRoot.safeItem.chip
                    kind: taskCardRoot.safeItem.kind || ""
                    Layout.preferredHeight: dp(24)
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    Layout.preferredWidth: dp(20)
                    Layout.preferredHeight: dp(20)
                    radius: width / 2
                    color: Qt.alpha(root.columnAccent(taskCardRoot.safeItem.kind || ""), 0.13)

                    NText {
                        anchors.centerIn: parent
                        text: root.taskAvatarText(taskCardRoot.safeItem)
                        color: root.columnAccent(taskCardRoot.safeItem.kind || "")
                        font.pointSize: fp(Style.fontSizeXS)
                        font.bold: true
                        applyUiScale: false
                    }
                }
            }
        }
    }

    component TaskChip: Item {
        id: taskChipRoot
        property string text
        property string kind
        readonly property color accent: root.chipAccent(text, kind)

        Layout.preferredWidth: chipLabel.implicitWidth + dp(28)

        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: Qt.alpha(taskChipRoot.accent, 0.13)
        }

        Row {
            anchors.centerIn: parent
            spacing: dp(4)

            NText {
                text: root.chipIcon(taskChipRoot.text)
                color: taskChipRoot.accent
                font.pointSize: fp(Style.fontSizeXS)
                font.bold: true
                applyUiScale: false
            }

            NText {
                id: chipLabel
                text: taskChipRoot.text
                color: taskChipRoot.accent
                font.pointSize: fp(Style.fontSizeXS)
                font.bold: true
                applyUiScale: false
            }
        }
    }
}
