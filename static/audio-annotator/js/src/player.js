function Player(height, freesound_id, sound_url, waveform_url, spectrogram_url)
{

    this.wavesurfer;
    this.playBar;
    this.fs_id = freesound_id;
    this.playerDom = "#s" + this.fs_id;
    this.height = height;
    this.ws_container = this.playerDom + " .wavesurfer";

    // Create wavesurfer object (playback and mouse interaction)
    this.wavesurfer = Object.create(WaveSurfer);
    this.wavesurfer.init({
        container: this.ws_container,
        height: this.height
    });

    // Create play bar
    this.playBar = new PlayBar(this);
    this.playBar.create();

    var height_px = this.height + "px";
    $(this.ws_container).find(".spectrogram").css({
        "height": height_px,
        "background-image": "url(" + spectrogram_url + ")",
        "background-repeat": "no-repeat",
        "background-size": "100% 100%"
    });

    $(this.ws_container).find(".waveform").css({
        "height": height_px,
        "background-image": "url(" + waveform_url + ")",
        "background-repeat": "no-repeat",
        "background-size": "100% 100%"
    });

    //this.wavesurfer.on('ready', function () {

    $(this.ws_container).children("wave").css({
        "width": "100%",
        "overflow": "hidden"
    });

            /*
            var controls_container = $(player_container + " .controls");
            var play_pause = $(player_container + " .controls .play_pause");

            $(player_container + " .controls .switch").click(function() {
                $(player_container + " .wavesurfer .waveform").toggle();
                $(player_container + " .wavesurfer .spectrogram").toggle();
            });
            */
    this.addEvents();

    this.wavesurfer.load(sound_url);

}

Player.prototype = {
    addEvents: function() {
        var pl = this;

        pl.wavesurfer.on("ready", function() {
            pl.playBar.update();
        });
    },

    switchView: function() {
        var pl = this;
        var view = $(pl.playerDom).find(".view");
        view.toggleClass("waveform");
        view.toggleClass("spectrogram");
    }
};

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
            class: "ui icon blue button play_pause"
        });
        var playIcon = $("<i>", {
            class: "play icon"
        });
        playButton.append(playIcon);
        playButton.click(function() {
            pl.wavesurfer.playPause();
        });

        // Create stop button
        var stopButton = $("<button>", {
            class: "ui icon blue button stop"
        });
        var stopIcon = $("<i>", {
            class: "stop icon"
        });
        stopButton.append(stopIcon);
        stopButton.click(function() {
           pl.wavesurfer.stop();
        });

        // Create switch view button
        var switchButton = $("<button>", {
            class: "ui red button switch"
        });
        var switchIcon = $("<i>", {
            class: "eye icon"
        });
        switchButton.append(stopIcon);
        switchButton.click(function () {
            pl.player.switchView();
        });
        /*
        var timer = $("<span>", {
            class: "timer",
        });
        */

        this.playBarDom = [playButton, stopButton, switchButton];
    },

    update: function() {
        pl = this;
        $(pl.playBarDom).detach();
        $(pl.playerDom).find(".controls").append(pl.playBarDom);
    },

    addWaveSurferEvents: function() {
        var pl = this;

        pl.wavesurfer.on("play", function () {
            var playerDom = pl.playerDom;
            var button = $(playerDom).find(".play_pause");
            button.find(".play").removeClass("play").addClass("pause");
        });

        pl.wavesurfer.on("pause", function () {
            var playerDom = pl.playerDom;
            var button = $(playerDom).find(".play_pause");
            button.find(".pause").removeClass("pause").addClass("play");
        });
    }

};