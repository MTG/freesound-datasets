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
        var node = tt.data;
        tt.ontology_tree = tt.addNode(node);
    },

    addNode: function (node, parent_name) {

        var tt = this;

        var category_info = {
            name: node.name,
            parent: parent_name || null,
            children: node.children
        };
        var category = new Category(category_info);
        var DOM = category.DOM;
        //tt.categories.push(category);

        if (category.hasChildren()) {
            var parent_node = node;
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
    this.last_child = !this.hasChildren();
    this.DOM = this.buildCategory();
    //this.children_DOM = this.DOM.find("list");

    /*
    this.description
    this.players
    this.external_link
    ...
     */
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
            class: "item expanded"
            // TODO: check if last child
            // TODO: 'expanded' and 'open' statuses
        });

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

        return category_DOM;

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

        return icon
    }

};