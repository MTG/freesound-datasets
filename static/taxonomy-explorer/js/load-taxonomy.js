/*
* ********************************
*         GENERAL TEMPLATE
* ********************************
* <div class="ui list">
*     <div class="item">...</div>      // category
*     <div class="item">...</div>      // category
*     <div class="item">...</div>      // category
*     <div class="item">...</div>      // category
*     ...
* </div>
*
*
* ************************
*         CATEGORY
* ************************
* <div class="item">
*     <i class="sitemap icon"></i>      // only if it has children
*     <div class="content">
*         <div class="header">
*             Category name
*             <button class="ui circular icon basic button">
*                 <i class="down chevron icon"></i>
*             </button>
*         </div>
*     </div>
* </div>
*
* */

function TaxonomyTree(Options) {
    this.url = Options.url;
    this.container = Options.container;
    this.skipCategories = Options.skipCategories || [];
    this.categories = [];
    this.id_to_idx = {};
    this.ontology_tree;
    this.data;
    this.openedCategories = [];
}

TaxonomyTree.prototype = {

    load: function () {
        var tt = this;
        $.getJSON(tt.url)
            .done(function (data) {
                tt.data = data;
                tt.update();
            })
    },

    update: function () {
        var tt = this;
        tt.buildTree();
        tt.showTree();
        console.log(tt.data);
    },

    buildTree: function () {
        var tt = this;
        var root = tt.data;
        $(tt.container).append(
            $("<div>", {
                class: "ui list"
            })
        );
        tt.ontology_tree = tt.addNode(root);
    },

    addNode: function (node, parent_name) {

        var tt = this;
        var skip_this = tt.skipCategories.indexOf(node.name) > -1;

        var category_info = {
            name: node.name,
            parent: parent_name || null,
            children: node.children,
            id: node.node_id,
            TT: tt
        };

        var category = new Category(category_info);
        var DOM = skip_this ? $(tt.container) : category.DOM;
        // uncomment next line to flatten the tree into a list
        tt.categories.push(category);
        tt.id_to_idx[category.id] = tt.categories.length -1;

        if (category.hasChildren()) {
            var parent_node = skip_this ? tt.data : node;
            var children_DOM_container = DOM.find(".list");
            $(parent_node.children).each(function () {
                // recursively build tree
                var child_DOM = tt.addNode(this, parent_node.name);
                children_DOM_container.append(child_DOM)
            });
        }

        return DOM;
    },

    showTree: function () {
        var tt = this;
        $(tt.container).append(tt.ontology_tree);
    },

    locateCategory: function(bigId) {
        var tt = this;
        this.collapseAll(function() {
            tt.openAndScroll(bigId);
        });
        // this.collapseAll();
        // this.openAndScroll(bigId);
    },

    openAndScroll: function (bigId) {
        var node_ids = bigId.split(',');
        for (var i=0; i<node_ids.length; i++) {
            var category = this.categories[this.id_to_idx[node_ids[i]]];
            if (!category.DOM.hasClass("expanded")) {
                category.toggleChildren();
            }
            if (i === node_ids.length-1) {
                category.toggleInfo(function() {
                    $('html, body').animate({
                        scrollTop: category.DOM.eq(0).offset().top - 60
                    }, 200);
                });
            }
        }
    },

    collapseAll: function (callback) {
        var tt = this;
        for (var i=0; i<tt.openedCategories.length; i++) {
            tt.openedCategories[i].closeChildren();
        }
        if (callback)
            setTimeout(function() {callback()}, 200);  // HERE TO SEQUENTIAL CALL, NOT THIS HACK!!
    }

};


function Category(Info) {
    this.name = Info.name;
    this.parent = Info.parent;      //TODO: more than one parent???
    this.children = Info.children;
    this.skipped = Info.skipped || false;
    this.expanded = Info.expanded || false;
    this.open = false;
    this.active_button = true;
    this.last_child = !this.hasChildren();
    this.DOM;
    this.id = Info.id;
    this.TT = Info.TT;

    this.buildCategory();
}

Category.prototype = {

    hasChildren: function () {
        return (this.children && this.children !== null)
    },

    toggleInfo: function (callback) {
        var ct = this;
        var href = "/fsd/node-info/" + ct.name;

        ct.active_button = false;

        if (!ct.DOM.hasClass("open")) {
            $.ajax({
                url: href,
                type: "GET",
                success: function(data) {
                    ct.showInfo(data);
                    if (callback)
                        setTimeout(function() {callback();}, 200)
                }
            });
        } else if (callback) {
            setTimeout(function() {callback();}, 200)
        }


    },

    showInfo: function (data) {
        var ct = this;
        var card = $(data);
        var content = ct.DOM.find(".content")[0];
        var hdr = $(content).find(".header")[0];

        $(hdr).fadeOut(100, function() {
            hdr = $(this).detach();
        });

        ct.DOM.addClass("open");
        card.css({
            "display": "none"
        });
        $(content).prepend(card);
        card.slideDown(200);

        var btn_close = $(card.find(".close-card")[0]);
        btn_close.click(function () {
            ct.hideInfo(card, hdr);
        });
    },

    hideInfo: function (card, header) {
        var ct = this;
        var content = ct.DOM.find(".content")[0];
        var btn = header.find("button")[0];

        if (!ct.last_child) {
            var children_list = $(content).find(".list")[0];
            $(content).append($(children_list).detach());
        }
        $(card).slideUp(200, function() {
            ct.DOM.removeClass("open");
            $(card).detach();
            $(content).prepend(header.fadeIn(100));
            ct.active_button = true;
            $(btn).prop("disabled", false);
        });
    },

    buildCategory: function () {

        /*
        * ************************
        *         CATEGORY
        * ************************
        * <div class="item">
        *     <i class="sitemap icon"></i>      // only if it has children
        *     <div class="content">
        *         <div class="header">
        *             Category name
        *             <button class="ui circular icon basic button">
        *                 <i class="down chevron icon"></i>
        *             </button>
        *         </div>
        *         <div class="list">            // only if it has children
        *             <div class="item>...</div>
        *             <div class="item>...</div>
        *             <div class="item>...</div>
        *         </div>
        *     </div>
        * </div>
        * */

        var ct = this;
        var category_name = ct.name;

        var category_DOM = $("<div>", {
            class: "item"
        });

        if (ct.last_child) {
            category_DOM.addClass("last");
        }
        if (ct.expanded) {
            category_DOM.addClass("expanded");
        }

        var category_icon = ct.buildCategoryIcon();

        var content = $("<div>", {
            class: "content"
        });

        var header = $("<div>", {
            class: "header",
            title: "Show additional info"
        });
        var header_link = $("<a>");

        var children_list = null;
        if (!ct.last_child) {
            children_list = $("<div>", {
                class: "list"
            });
            if (!ct.expanded) {
                children_list.css({
                    "display": "none"
                });
            }
        }

        var show_info = $("<button>", {
            class: "ui circular icon basic button"
        });

        var show_info_icon = $("<i>", {
            class: "down chevron icon"
        });

        header.click(function () {
            if (ct.active_button) {
                show_info.prop("disabled", true);
                ct.toggleInfo();
            }
        });

        show_info.append(show_info_icon);
        header_link.append(category_name);
        header.append([header_link, show_info]);
        content.append([header, children_list]);
        category_DOM.append([category_icon, content]);

        ct.DOM = category_DOM;
    },

    toggleChildren: function () {
        var ct = this;
        if (!ct.last_child) {
            ct.DOM.hasClass("expanded") ? ct.closeChildren() : ct.openChildren();
        }

    },

    openChildren: function () {
        var ct = this;
        ct.DOM.toggleClass("expanded");
        var children_list = ct.DOM.children(".content").children(".list");
        children_list.slideDown(500, "swing");
        ct.DOM.children(".icon").attr("title", "Collapse children categories");
        ct.TT.openedCategories.push(ct);
    },

    closeChildren: function () {
        var ct = this;
        var children_list = ct.DOM.children(".content").children(".list");
        children_list.slideUp(500, "swing", function() {
            ct.DOM.toggleClass("expanded");
        });
        ct.DOM.children(".icon").attr("title", "Expand children categories");
        ct.TT.openedCategories.splice(ct.TT.openedCategories.indexOf(ct));
    },

    buildCategoryIcon: function () {
        var ct = this;
        var class_name,
            title;

        if (ct.hasChildren()) {
            class_name = "sitemap icon";
            title = "Expand children categories";
        }
        else {
            class_name = "circle icon";
            title = "This category has no children";
        }

        var icon = $("<i>", {
            class: class_name,
            title: title
        });

        icon.click(function () {
            ct.toggleChildren();
        });

        return icon;
    }

};