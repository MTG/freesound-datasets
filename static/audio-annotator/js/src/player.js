// Player prototype
function Player(Options)
{
    this.wavesurfer;
    this.playBar;
    this.view;
    this.fs_id = Options.freesound_id;
    this.player_id = Options.player_id;
    this.playerDom = "#s" + this.fs_id + "_" + this.player_id;
    this.size = Options.size || "medium";
    this.height = Options.height || this.getHeightFromSize(this.size);
    this.ws_container = this.playerDom + " .wavesurfer";
    this.spectrogram = Options.spectrogram_url;
    this.waveform = Options.waveform_url;
    this.sound_url = Options.sound_url;
    this.ready = false;

    this.setupWaveSurferInstance();

    // Create wavesurfer object (playback and mouse interaction)
    this.wavesurfer = Object.create(WaveSurfer);
    this.wavesurfer.init({
        container: this.ws_container,
        height: this.height,
        audioContext: this.getAudioContext()
    });

    // Create view
    this.view = new View(this);
    this.view.create();

    // Create play bar
    this.playBar = new PlayBar(this);
    this.playBar.create();

    $(this.ws_container).children("wave").css({
        "width": "100%",
        "overflow": "hidden"
    });

    this.addEvents();
    this.load();
}

Player.prototype = {
    load: function() {
        var pl = this;
        pl.wavesurfer.load(pl.sound_url);
    },

    addEvents: function() {
        var pl = this;

        pl.wavesurfer.on("ready", function () {
            // Make sure the loader is removed only after
            // loading all the GUI components
            $.when(
                pl.view.update(),
                pl.playBar.update()
            ).then(
                pl.removeLoader(),
                pl.ready = true
            );
        });
    },

    removeLoader: function() {
        var pl = this;
        $(pl.playerDom).find(".dimmer").removeClass("active");
    },
    
    getAudioContext: function () {
        if (!window.audioCtx) {
            window.audioCtx = new (
                window.AudioContext || window.webkitAudioContext
            );
        }
        return window.audioCtx;
    },

    getHeightFromSize: function (size) {
        var height;

        switch (size) {
            case "mini":
                height = 70;
                break;
            case "small":
                height = 80;
                break;
            case "medium":
                height = 100;
                break;
            case "big":
                height = 200;
                break;
            default:
                // medium
                height = 100;
        }

        return height;
    },

    stop: function () {
        var pl = this;
        if (pl.wavesurfer.isPlaying()) {
            pl.wavesurfer.stop();
        }
    },

    setupWaveSurferInstance: function () {

        WaveSurfer.drawBuffer = function () {
            // empty function, do not draw buffer
        };

        WaveSurfer.createDrawer = function () {
            this.drawer = Object.create(WaveSurfer.Drawer[this.params.renderer]);
            this.drawer.init(this.container, this.params);
        }
    },

    destroy: function () {
        var pl = this;
        if(window.activePlayer && window.activePlayer === pl) {
            window.activePlayer = null;
        }
        pl.stop();
        if (pl.ready) {
            pl.wavesurfer.destroy();
        }
    }
};

// View prototype
function View(player) {
    this.player = player;
    this.playerDom = this.player.playerDom;
    this.wavesurfer = this.player.wavesurfer;
    this.ws_container = this.player.ws_container;
    this.height = this.player.height;
    this.spectrogram = this.player.spectrogram;
    this.waveform = this.player.waveform;
    this.viewDom = null;
    this.clickable = $(this.ws_container).find("> wave");
    this.progressBar = $(this.ws_container).find("wave wave");
    this.progressBar.addClass("progress-bar");
}

View.prototype = {
    create: function () {
        var pl = this;
        pl.addEvents();

        // Create background element
        var height_px = pl.height + "px";
        var viewBckg = $("<div>", {
            class: "view spectrogram"
        });

        // This trick loads the image before setting it as background
        var img = $("<img/>", {
            src: pl.spectrogram
        });
        img.on("load", function () {
            $(this).remove();
            viewBckg.css({
                "height": height_px,
                "background-image": "url(" + pl.spectrogram + ")",
                "background-repeat": "no-repeat",
                "background-size": "100% 100%"
            });
        });

        pl.viewDom = [viewBckg];
    },

    switch: function () {
        var pl = this;
        var view = $(pl.ws_container).find(".view");
        var bckg_img = (view.hasClass("spectrogram") ? pl.waveform : pl.spectrogram);
        view.toggleClass("spectrogram").toggleClass("waveform");
        view.css({
            "background-image": "url(" + bckg_img + ")"
        });
    },

    update: function() {
        pl = this;
        $(pl.viewDom).detach();
        $(pl.ws_container).append(pl.viewDom);
    },

    getHorizontalCoordinates: function(e) {
        var pl = this;
        var offset = pl.clickable.offset();
        var width = pl.clickable.width();
        return (e.pageX - offset.left) / width;
    },

    updateProgressBar: function(pos) {
        var pl = this;
        var progress = pos || pl.wavesurfer.getCurrentTime() / pl.wavesurfer.getDuration();
        progress *= 100;

        pl.progressBar.css({
            "width": progress + "%"
        });
    },

    addEvents: function () {
        var pl = this;
        pl.addWaveSurferEvents();

        // Other events
        pl.clickable.on("click", function (e) {
            var x = pl.getHorizontalCoordinates(e);
            pl.wavesurfer.seekTo(x);
            pl.updateProgressBar(x);
        })
    },

    addWaveSurferEvents: function () {
        var pl = this;

        pl.wavesurfer.on("audioprocess", function () {
            pl.updateProgressBar();
        });

        pl.wavesurfer.on("finish", function () {
            pl.updateProgressBar();
        });
    }
};

// Play bar prototype
function PlayBar(player) {
    this.player = player;
    this.playerDom = this.player.playerDom;
    this.wavesurfer = this.player.wavesurfer;
    this.playBarDom = null;
}

PlayBar.prototype = {
    create: function() {
        var pl = this;
        pl.addWaveSurferEvents();

        // Create play button
        var playButton = $("<button>", {
            class: "ui icon button play_pause",
            type: "button",
            title: "Play/pause clip"
        });
        var playIcon = $("<i>", {
            class: "play icon"
        });
        playButton.append(playIcon);
        playButton.click(function() {
            pl.wavesurfer.playPause();
        });

        // Create stop button
        var restartButton = $("<button>", {
            class: "ui icon button restart",
            type: "button",
            title: "Restart clip"
        });
        var restartIcon = $("<i>", {
            class: "step backward icon"
        });
        restartButton.append(restartIcon);
        restartButton.click(function() {
           pl.wavesurfer.stop();
           pl.wavesurfer.play();
        });

        // Create switch view button
        var switchButton = $("<button>", {
            class: "ui icon button switch",
            type: "button",
            title: "Switch view"
        });
        var switchIcon = $("<i>", {
            class: "eye icon"
        });
        switchButton.append(switchIcon);
        switchButton.click(function () {
            pl.player.view.switch();
        });

        var controls = [playButton, restartButton, switchButton];

        var floatClass = "";
        if (pl.player.size !== "small" && pl.player.size !== "mini") {
            floatClass = " left floated";
        }
        var controlsDiv = $("<div>", {
            class: "ui controls-container" + floatClass
        });
        var controlsInnerDiv = $("<div>", {
            class: "ui horizontal buttons controls"
        });
        controlsInnerDiv.append(controls);
        controlsDiv.append(controlsInnerDiv);

        // Create timer indicator
        floatClass = "";
        if (pl.player.size !== "small" && pl.player.size !== "mini") {
            floatClass = " right floated";
        }
        var timerDiv = $("<div>", {
            class: "ui timer-container" + floatClass
        });
        var timer = $("<span>", {
            class: "timer"
        });
        timerDiv.append(timer);

        pl.playBarDom = [controlsDiv, timerDiv];
    },

    update: function() {
        pl = this;
        $(pl.playBarDom).detach();
        $(pl.playerDom).find(".playbar").addClass("active").append(pl.playBarDom);
        pl.updateTimer();
    },

    updateTimer: function() {
        pl = this;
        timerText = pl.getTimerText();
        $(pl.playerDom).find(".playbar").find(".timer").text(timerText);
    },

    getTimerText: function() {
        var pl = this;
        var secondsToString = function (seconds) {
            if (seconds === null || seconds < 0) {
                return '';
            }
            var timeStr;
            var minutes = Math.floor(seconds / 60);
            if (minutes >= 10) {
                timeStr = minutes;
            } else {
                timeStr = '0' + minutes;
            }
            timeStr += ':';
            var secs = Math.round(seconds - (minutes * 60));
            if (secs >= 10) {
                timeStr += secs;
            } else {
                timeStr += '0' + secs;
            }
            return timeStr;
        };

        return secondsToString(pl.wavesurfer.getCurrentTime()) +
            ' / ' + secondsToString(pl.wavesurfer.getDuration());
    },

    addWaveSurferEvents: function() {
        var pl = this;

        pl.wavesurfer.on("play", function () {
            var playerDom = pl.playerDom;
            var button = $(playerDom).find(".play_pause");
            // Stop all and store current player
            if(window.activePlayer && window.activePlayer !== pl.player)
                window.activePlayer.wavesurfer.stop();
            window.activePlayer = pl.player;
            // Change icon
            button.find(".play").removeClass("play").addClass("pause");
        });

        pl.wavesurfer.on("pause", function () {
            var playerDom = pl.playerDom;
            var button = $(playerDom).find(".play_pause");
            // Change icon
            button.find(".pause").removeClass("pause").addClass("play");
        });

        pl.wavesurfer.on("seek", function () {
            pl.updateTimer();
            pl.player.view.updateProgressBar();
        });

        pl.wavesurfer.on("audioprocess", function () {
            pl.updateTimer();
        });
    }
};