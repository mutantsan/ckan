ckan.module("ckan-admin-tabulator", function ($, _) {
    "use strict";
    return {
        templates: {
            btnFullscreen: `<a class='btn btn-default d-none d-sm-inline-block' id='btn-fullscreen' title='Fullscreen toggle'><i class='fa fa-expand'></i></a>`,
        },
        options: {
            config: null,
            enableFullscreenToggle: true
        },

        initialize: function () {
            $.proxyAll(this, /_/);

            if (!this.options.config) {
                return console.error("No config provided for tabulator");
            }

            this.filterField = document.getElementById("filter-field");
            this.filterOperator = document.getElementById("filter-operator");
            this.filterValue = document.getElementById("filter-value");
            this.filterClear = document.getElementById("filter-clear");
            this.globalAction = document.getElementById("global-action");
            this.applyGlobalAction = document.getElementById("apply-global-action");
            this.tableWrapper = document.querySelector(".tabulator-wrapper");

            // Update filters on change
            this.filterField.addEventListener("change", this._onUpdateFilter);
            this.filterOperator.addEventListener("change", this._onUpdateFilter);
            this.filterValue.addEventListener("keyup", debounce(this._onUpdateFilter, 500));
            this.filterClear.addEventListener("click", this._onClearFilter);

            if (this.applyGlobalAction) {
                this.applyGlobalAction.addEventListener("click", this._onApplyGlobalAction);
            }

            this.sandbox.subscribe("ap:tabulator:refresh", this._refreshData);

            this.options.config.footerElement = this.templates.btnFullscreen;
            this.options.config.ajaxParams = () => {
                return {
                    field: this.filterField.value,
                    operator: this.filterOperator.value,
                    q: this.filterValue.value,
                };
            };

            this.table = new Tabulator(this.el[0], this.options.config);

            this.table.on("tableBuilt", () => {
                this._onUpdateFilter();

                if (this.options.enableFullscreenToggle) {
                    this.btnFullscreen = document.getElementById("btn-fullscreen");
                    this.btnFullscreen.addEventListener("click", this._onFullscreen);
                }
            });

            this.table.on("renderComplete", function () {
                htmx.process(this.element);

                const pageSizeSelect = document.querySelector(".tabulator-page-size");

                if (pageSizeSelect) {
                    pageSizeSelect.classList.add("form-select");
                }
            });
        },

        /**
         * Update the filter based on the selected field, operator and value
         */
        _onUpdateFilter: function () {
            this.table.replaceData();
            this._updateUrl();
        },

        /**
         * Clear the filter
         */
        _onClearFilter: function () {
            this.filterField.value = "";
            this.filterOperator.value = "=";
            this.filterValue.value = "";

            this.table.replaceData();
            this._updateUrl();
        },

        /**
         * Update the URL with the current filter values
         */
        _updateUrl: function () {
            const url = new URL(window.location.href);
            url.searchParams.set("field", this.filterField.value);
            url.searchParams.set("operator", this.filterOperator.value);
            url.searchParams.set("q", this.filterValue.value);
            window.history.replaceState({}, "", url);
        },

        /**
         * Apply the global action to the selected rows
         */
        _onApplyGlobalAction: function () {
            const globalAction = this.globalAction.options[this.globalAction.selectedIndex].value;

            if (!globalAction) {
                return;
            }

            ckan.confirm({
                message: ckan.i18n._("Are you sure you want to perform this action?"),
                onConfirm: () => this._onGlobalActionConfirm(globalAction)
            });
        },

        _onGlobalActionConfirm: function (globalAction) {
            const selectedData = this.table.getSelectedData();

            if (!selectedData.length) {
                return;
            }

            // exclude 'actions' column
            const data = selectedData.map(row => {
                const { actions, ...rest } = row;
                return rest;
            });

            const form = new FormData();

            const csrf_field = $('meta[name=csrf_field_name]').attr('content');
            const csrf_token = $('meta[name=' + csrf_field + ']').attr('content');

            form.append("global_action", globalAction);
            form.append("rows", JSON.stringify(data));

            fetch(this.sandbox.client.url(this.options.config.ajaxURL), {
                method: "POST",
                body: form,
                headers: {
                    'X-CSRFToken': csrf_token
                }
            })
                .then(resp => resp.json())
                .then(resp => {
                    if (!resp.success) {
                        ckan.toast({ message: resp.errors[0], type: "danger" });

                        if (resp.errors.length > 1) {
                            ckan.toast({
                                message: ckan.i18n._("Multiple errors occurred and were suppressed"),
                                type: "error"
                            });
                        }
                    }

                    this._refreshData()
                    ckan.toast({
                        message: ckan.i18n._("Operation completed"),
                        title: ckan.i18n._("Notification"),
                    });
                }).catch(error => {
                    console.error("Error:", error);
                });
        },

        _refreshData: function () {
            this.table.replaceData();
        },

        _onFullscreen: function () {
            const isFullscreen = this.tableWrapper.classList.contains("fullscreen");

            if (isFullscreen) {
                this.tableWrapper.classList.remove("fullscreen");
            } else {
                this.tableWrapper.classList.add("fullscreen");
            }
        },
    };
});

function debounce(func, delay) {
    let timeout;
    return function (...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
    };
}
