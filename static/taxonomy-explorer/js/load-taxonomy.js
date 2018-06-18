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
    this.ontology_tree;
    this.data;
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
            children: node.children
        };

        var category = new Category(category_info);
        var DOM = skip_this ? $(tt.container) : category.DOM;
        // uncomment next line to flatten the tree into a list
        //tt.categories.push(category);

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
    }

};


function Category(Info) {
    this.name = Info.name;
    this.parent = Info.parent;      //TODO: more than one parent???
    this.children = Info.children;
    this.skipped = Info.skipped || false;
    this.expanded = Info.expanded || false;
    this.open = false;
    this.last_child = !this.hasChildren();
    this.DOM;

    this.buildCategory();
}

Category.prototype = {

    hasChildren: function () {
        return (this.children && this.children !== null)
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
            // TODO: 'open' status
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
            class: "header"
        });

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

        show_info.append(show_info_icon);
        header.append([category_name, show_info]);
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
    },

    closeChildren: function () {
        var ct = this;
        var children_list = ct.DOM.children(".content").children(".list");
        children_list.slideUp(500, "swing", function() {
            ct.DOM.toggleClass("expanded");
        });
    },

    buildCategoryIcon: function () {

        var ct = this;
        var class_name;

        if (ct.hasChildren()) {
            class_name = "sitemap icon";
        }
        else {
            class_name = "circle icon";
        }

        var icon = $("<i>", {
            class: class_name
        });

        icon.click(function () {
            ct.toggleChildren();
        });

        return icon
    }

};