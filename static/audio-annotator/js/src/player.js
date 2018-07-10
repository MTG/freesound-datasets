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
    this.error_dimmer = null;
    this.N_MAX_ATTEMPTS = 3;
    // For testing normalization methods
    this.loudness_normalization_ratio = parseFloat(Options.loudness_normalization_ratio);

    this.setupWaveSurferInstance();

    // Create wavesurfer object (playback and mouse interaction)
    this.options = {
        container: this.ws_container,
        height: this.height,
        audioContext: this.getAudioContext()
    };
    this.wavesurfer = WaveSurfer.create(this.options);

    // Create view
    this.view = new View(this);
    this.view.create();

    // Create play bar
    this.playBar = new PlayBar(this);
    this.playBar.create();

    // Create processor
    this.processor = new Processor(this);

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
        //console.log(pl.sound_url);
        pl.wavesurfer.load(pl.sound_url);
    },

    reloadSound: function () {
        var pl = this;
        pl.removeErrorMessage();
        pl.addLoader();
        pl.view.createBackground();
        pl.addEvents();
        pl.load();
    },

    addEvents: function() {
        var pl = this;
        var attempts = pl.N_MAX_ATTEMPTS;

        pl.wavesurfer.on("ready", function () {
            // Make sure the loader is removed only after
            // loading all the GUI components
            $.when(
                pl.view.update(),
                pl.playBar.update()
            ).then(
                pl.removeLoader(),
                pl.normalizeVolume(),
                pl.ready = true
            );
        });

        pl.wavesurfer.on("error", function (e) {
            console.log(e);
            //console.log("Player: " + pl.fs_id);
            if (attempts) {
                attempts--;
                // Next line for testing, to be removed
                //pl.sound_url = pl.sound_url.substring(1);
                //
                if(e === "Error decoding audiobuffer") {
                    console.log("Trying another format...");
                    pl.tryOtherFormat();
                }
                setTimeout(function() {
                    pl.load();
                }, 500);
            } else {
                attempts = pl.N_MAX_ATTEMPTS;
                pl.removeLoader();
                pl.addErrorMessage();
            }
        });
    },

    addLoader: function() {
        var pl = this;
        $(pl.playerDom).find(".load-dimmer").addClass("active");
    },

    removeLoader: function() {
        var pl = this;
        $(pl.playerDom).find(".load-dimmer").removeClass("active");
    },

    addErrorMessage: function() {
        var pl = this;
        if (!pl.error_dimmer) {
            pl.error_dimmer = pl.view.createErrorMessage();
        }
        $(pl.playerDom).prepend(pl.error_dimmer);
    },

    removeErrorMessage: function() {
        var pl = this;
        if (pl.error_dimmer) {
            pl.error_dimmer.detach();
        }
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

    normalizeVolume: function () {
        var pl = this;
        var factor = this.loudness_normalization_ratio;

        if (pl.processor.isClipping(factor)) {
            console.log("Clipping!!");
        }

        gain = Math.min(factor, pl.processor.getFactorForFullScale());
        //gain = factor;

        // console.log("calculated factor: ", factor);
        // console.log("factor for full scale: ", pl.processor.getFactorForFullScale());
        // console.log("selected factor: " + gain);

        pl.wavesurfer.setVolume(gain);
    },
  
    stop: function () {
        var pl = this;
        if (pl.wavesurfer.isPlaying()) {
            pl.wavesurfer.stop();
        }
    },

    setupWaveSurferInstance: function () {
        WaveSurfer.prototype.drawBuffer = function () {
            // empty function, do not draw buffer
        };

        WaveSurfer.prototype.createDrawer = function () {
            this.drawer = new this.Drawer(this.container, this.params);
            this.drawer.init();
        };

    },

    tryOtherFormat: function() {
        var pl = this;
        var url = pl.sound_url;
        var splitted = url.split("/");
        var format = splitted[splitted.length - 1].split('.')[1];
        var new_format = '';
        switch (format) {
            case 'mp3':
                new_format = '.ogg';
                break;
            case 'ogg':
                new_format = '.mp3';
                break;
            default:
                new_format = '.ogg';
        }
        pl.sound_url = pl.sound_url.split('.' + format)[0] + new_format;
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

    this.clickable.addClass("clickable");
    this.progressBar.addClass("progress-bar");
}

View.prototype = {
    create: function () {
        var pl = this;

        pl.createBackground();
        pl.addEvents();
    },

    createBackground: function () {
        var pl = this;

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
    },

    createErrorMessage: function () {
        var pl = this;

        // Create gray overlay
        var dimmer = $("<div>", {
            class: "ui dimmer active player-error"
        });
        var content = $("<div>", {
            class: "content"
        });

        // Create background icon
        var errIcon = $("<i>", {
            class: "exclamation circle icon"
        });

        // Create error description
        var errDescription = $("<div>", {
            class: "error-description"
        });
        var errTitle = $("<h4>", {
            class: "ui inverted sub header"
        });
        errTitle.append(
            "Something's wrong :-("
        );
        var errMsg = $("<p>", {
            class: "ui inverted error-message"
        }).text("Try reloading the player.");

        // Create reload button
        var reloadBtn = $("<button>", {
            type: "button",
            class: "ui inverted labeled icon basic mini button reload-sound"
        }).append(
            $("<i>", {
                class: "inverted undo icon"
            }),
            "Reload"
        );
        reloadBtn.click(function () {
            pl.player.reloadSound()
        });

        errDescription.append(errTitle, errMsg, reloadBtn);
        content.append(errIcon, errDescription);
        dimmer.append(content);

        return dimmer;
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

        var controlsDiv = $("<div>", {
            class: "ui controls-container"
        });
        var controlsInnerDiv = $("<div>", {
            class: "ui horizontal buttons controls"
        });
        controlsInnerDiv.append(controls);
        controlsDiv.append(controlsInnerDiv);

        // Create timer indicator
        var timerDiv = null;
        if (pl.player.size !== "mini") {
            timerDiv = $("<div>", {
                class: "ui timer-container"
            });
            var timer = $("<span>", {
                class: "timer"
            });
            timerDiv.append(timer);
        }

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
        var with_milliseconds = pl.player.size === "big";
        timerText = pl.getTimerText(with_milliseconds);
        $(pl.playerDom).find(".playbar").find(".timer").text(timerText);
    },

    getTimerText: function (with_milliseconds) {
        var pl = this;
        var secondsToString = function (seconds) {
            if (seconds === null || seconds < 0) {
                return '';
            }

            var minutes = Math.floor(seconds / 60);
            var timeStr = minutes;

            timeStr += ':';
            var secs = seconds - (minutes * 60);

            secs = with_milliseconds ?
                secs.toFixed(2) : Math.round(secs);

            timeStr += secs >= 10 ? secs : '0' + secs;
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

// Signal processor prototype
// (implements some basic DSP routines, such as RMS normalization)
function Processor(player) {
    this.player = player;
    this.wavesurfer = this.player.wavesurfer;
    this.REFERENCE_RMS = Math.pow(10, -23.0/20);
}

Processor.prototype = {
    create: function() {},

    normalizeRMS: function(targetRMS) {
        var pl = this;
        var signal = pl.getPCM();
        var RMS = pl.rootMeanSquare(signal);
        var target = targetRMS || pl.REFERENCE_RMS;

        return target / RMS;
    },

    getFactorForFullScale: function () {
        var pl = this;
        var maxVal = pl.getMaxSampleValue(pl.getPCM());
        return 0.8 / maxVal;
    },

    isClipping: function(gain) {
        var pl = this;
        var maxVal = pl.getMaxSampleValue(pl.getPCM());
        // console.log("Max value: ", maxVal);
        // console.log("Max value with gain: ", maxVal * gain);
        return maxVal * gain > 1;
    },

    getPCM: function() {
        var pl = this;
        var PCM = pl.wavesurfer.exportPCM(
            length = 4096,
            accuracy = 1000,
            noWindow = true,
            start = 0
        );

        return JSON.parse(PCM);
    },

    rootMeanSquare: function(signal) {
        var sig = signal || this.getPCM();

        var sumOfSquares = sig.reduce(function (s, x) {
            return (s + x * x);
        }, 0);

        return Math.sqrt(sumOfSquares / sig.length);
    },

    getMaxSampleValue: function(signal) {
        return Math.max.apply(null, signal.map(Math.abs))
    }
};