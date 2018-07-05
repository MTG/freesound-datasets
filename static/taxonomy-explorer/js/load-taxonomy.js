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
    this.generation_task = Options.generation_task;
    this.categories = [];
    this.id_to_idx = {};
    this.ontology_tree;
    this.data;
    this.openedCategories = [];
    this.infoCategories = [];
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

    addNode: function (node, path, bigId) {
        var tt = this;
        var skip_this = tt.skipCategories.indexOf(node.name) > -1;
        var cur_path = path || [];
        var cur_bigId = bigId || '';

        var category_info = {
            name: node.name,
            path: cur_path,
            children: node.children,
            id: node.node_id,
            TT: tt,
            bigId: cur_bigId
        };

        var category = new Category(category_info);
        var DOM = skip_this ? $(tt.container) : category.DOM;
        tt.categories.push(category);
        tt.id_to_idx[cur_bigId] = tt.categories.length -1;

        if (category.hasChildren()) {
            var parent_node = skip_this ? tt.data : node;
            var children_DOM_container = DOM.find(".list");
            $(parent_node.children).each(function () {
                // recursively build tree
                var new_path = cur_path.concat([this.name]);
                var new_bigId = (cur_bigId === '') ? this.node_id: cur_bigId + ',' + this.node_id;
                var child_DOM = tt.addNode(this, new_path, new_bigId);
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

        tt.collapseAll()
            .then(function () {
                tt.openCategoryPath(bigId)
            })
            .then(function () {
                tt.scrollToCategory(bigId)
            })
        // TODO: add showInfo
    },

    openCategoryPath: function (bigId) {
        var tt = this;
        var node_ids = bigId.split(',');
        var proms = [];
        var id = '';
        for (var i = 0; i < node_ids.length; i++) {
            id += (i === 0) ? node_ids[i] : ',' + node_ids[i];
            var category = tt.categories[tt.id_to_idx[id]];
            if (!category.expanded) {
                proms.push(category.openChildren());
            }
        }

        return Promise.all(proms);
    },

    scrollToCategory: function (bigId) {
        var tt = this;
        var cat_idx = tt.id_to_idx[bigId];
        var category = tt.categories[cat_idx];
        var body = $('html, body');
        return body.stop().animate({
            scrollTop: category.DOM.offset().top-300
        }, 200).promise();
    },

    collapseAll: function () {
        var tt = this;
        var proms = [];
        return Promise.all(proms.concat(
            tt.collapseAllCategories(),
            tt.hideAllInfo()
        ));
    },

    collapseAllCategories: function () {
        var tt = this;
        var proms = [];
        for (var i = 0; i < tt.openedCategories.length; i++) {
            var category = tt.openedCategories[i];
            if (category.expanded)
                proms.push(category.closeChildren());
        }
        return proms;
    },

    hideAllInfo: function () {
        var tt = this;
        var proms = [];
        for (var i = 0; i < tt.infoCategories.length; i++) {
            var category = tt.infoCategories[i];
            proms.push(category.hideInfo());
        }
        return proms;
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
    this.path = Info.path;
    this.bigId = Info.bigId;
    this.hdr;

    this.buildCategory();
}

Category.prototype = {

    hasChildren: function () {
        return (this.children && this.children !== null)
    },

    toggleInfo: function () {
        var ct = this;
        var href = "/fsd/node-info/" + ct.name
            + '?gen-task=' + this.TT.generation_task;

        ct.active_button = false;

        if (!ct.DOM.hasClass("open")) {
            $.ajax({
                url: href,
                type: "GET",
                success: function (data) {
                    ct.showInfo(data);
                }
            });
        } else if (ct.DOM.hasClass("open")) {
            ct.hideInfo();
        }
    },

    showInfo: function (data) {
        var ct = this;
        var card = $(data);
        var content = ct.DOM.find(".content")[0];
        ct.hdr = $(content).find(".header")[0];

        // hide old header
        $(ct.hdr).fadeOut(100, function() {
            ct.hdr = $(this).detach();
        });

        // create breadcrumb
        var breadcrumb = $(content).find(".breadcrumb")[0];
        for (var i = 0; i < ct.path.length; i++) {
            var section = (i === ct.path.length-1) ? $("<div>", { class: "active" }) : $("<div>");
            section.addClass("section");
            var chevron = $("<i>", {
                class: "right angle icon divider"
            });
            section.append(ct.path[i]);
            $(breadcrumb).append([chevron, section]);
        }

        // create close button
        var btn_close = $(card.find(".close-card")[0]);
        btn_close.click(function () {
            ct.hideInfo(/*card*/);
        });

        // if generation task, create "Add" button
        if (ct.TT.generation_task === 1) {
            var btn_add = $(card.find(".add-label").eq(0));
            btn_add.click(function () {
                $("#label-container").append("<div style='margin: 2px;' class='added-label ui message' label-name='"+ ct.name +"''><i class='close icon'></i>"+ ct.name +"</div>")
                $('.message .close').on('click', function() {
                    $(this).parent('.message').remove();
                });
            });
        }

        // add classes and show card
        ct.DOM.addClass("open");
        card.css({
            "display": "none"
        });
        $(content).prepend(card);
        return card.slideDown(200, function () {
            ct.TT.infoCategories.push(ct);
        }).promise();
    },

    hideInfo: function () {
        var ct = this;
        var content = ct.DOM.find(".content")[0];
        var header = ct.hdr;
        var btn = header.find("button")[0];
        var card = ct.DOM.find(".ui.card")[0];

        if (!ct.last_child) {
            var children_list = $(content).find(".list")[0];
            $(content).append($(children_list).detach());
        }

        return $(card).slideUp(200, function() {
            ct.DOM.removeClass("open");
            $(card).detach();
            $(content).prepend(header.fadeIn(100));
            ct.active_button = true;
            $(btn).prop("disabled", false);
            ct.TT.infoCategories.splice(ct.TT.infoCategories.indexOf(ct));
        }).promise();
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
            ct.expanded ? ct.closeChildren() : ct.openChildren();
        }
    },

    openChildren: function () {
        var ct = this;
        if (ct.expanded || ct.last_child)
            return;
        ct.DOM.addClass("expanded");
        var children_list = ct.DOM.children(".content").children(".list")[0];
        return $(children_list).slideDown(300, "swing", function () {
            ct.TT.openedCategories.push(ct);
            ct.DOM.children(".icon").attr("title", "Collapse children categories");
            ct.expanded = true;
        }).promise();
    },

    closeChildren: function () {
        var ct = this;
        if (!ct.expanded)
            return;
        var children_list = ct.DOM.children(".content").children(".list")[0];
        return $(children_list).slideUp(300, "swing", function() {
            ct.DOM.removeClass("expanded");
            ct.TT.openedCategories.splice(ct.TT.openedCategories.indexOf(ct));
            ct.DOM.children(".icon").attr("title", "Expand children categories");
            ct.expanded = false;
        }).promise();
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

function asyncFunc(f) {
    return new Promise(function (resolve, reject) {
        resolve(f);
    });
}

function makePromise(fn, context, args) {
    return new Promise(function (resolve, reject) {
        res = fn.apply(context, args);
        resolve(res);
    });
}

function toggleChildrenChain(arr) {
    return arr.reduce(
        function (promise, item) {
            return promise.then(
                function (result) {
                    var category = TT.categories[TT.id_to_idx[item]];
                    if (!category.DOM.hasClass("expanded")) {
                        category.toggleChildren();
                    }
                    return asyncFunc(item);
                }
            )
            .catch(console.error);
        }, Promise.resolve()
    );
}
