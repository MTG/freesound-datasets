// Player prototype
function Player(Options)
{
    this.wavesurfer;
    this.playBar;
    this.view;
    this.fs_id = Options.freesound_id;
    this.playerDom = "#s" + this.fs_id;
    this.height = Options.height;
    this.ws_container = this.playerDom + " .wavesurfer";
    this.spectrogram = Options.spectrogram_url;
    this.waveform = Options.waveform_url;
    this.sound_url = Options.sound_url;

    // Create wavesurfer object (playback and mouse interaction)
    this.wavesurfer = Object.create(WaveSurfer);
    this.wavesurfer.init({
        container: this.ws_container,
        height: this.height
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

    this.wavesurfer.load(this.sound_url);
}

Player.prototype = {
    addEvents: function() {
        var pl = this;
        pl.wavesurfer.on("ready", function() {
            pl.playBar.update();
        });
    },
};

Player.activePlayer = null;

// View prototype
function View(player) {
    this.player = player;
    this.playerDom = this.player.playerDom;
    this.wavesurfer = this.player.wavesurfer;
    this.ws_container = this.player.ws_container;
    this.height = this.player.height;
    this.spectrogram = this.player.spectrogram;
    this.waveform = this.player.waveform;
}

View.prototype = {
    create: function () {
        var pl = this;
        // TODO: pl.createWaveSurferEvents

        // Create background element
        var view_el = $("<div>", {
            class: "view spectrogram"
        });
        var height_px = pl.height + "px";
        view_el.css({
            "height": height_px,
            "background-image": "url(" + pl.spectrogram + ")",
            "background-repeat": "no-repeat",
            "background-size": "100% 100%"
        });
        $(pl.ws_container).append(view_el);
    },

    switch: function () {
        var pl = this;
        var view = $(pl.ws_container).find(".view");
        var bckg_img = (view.hasClass("spectrogram") ? pl.waveform : pl.spectrogram);
        view.toggleClass("spectrogram").toggleClass("waveform");
        view.css({
            "background-image": "url(" + bckg_img + ")",
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
            class: "ui icon red button switch"
        });
        var switchIcon = $("<i>", {
            class: "eye icon"
        });
        switchButton.append(switchIcon);
        switchButton.click(function () {
            pl.player.view.switch();
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
            // Stop all and store current player
            if(Player.activePlayer !== null)
                Player.activePlayer.wavesurfer.stop();
            Player.activePlayer = pl.player;
            // Change icon
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