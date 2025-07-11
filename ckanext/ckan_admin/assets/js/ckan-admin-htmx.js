ckan.module("ckan-admin-htmx", function ($) {
    return {
        initialize: function () {
            $.proxyAll(this, /_on/);

            htmx.on("htmx:confirm", this._onHTMXconfirm);
            htmx.on("htmx:afterSwap", this._onAfterSwap);
        },

        /**
         * Handle the confirm dialog for HTMX with CKAN confirm dialog
         *
         * @param {Event} event The HTMX event
         */
        _onHTMXconfirm: function (event) {
            console.log(event);

            // The event is triggered on every trigger for a request, so we need to check if the element
            // that triggered the request has a confirm question set via the hx-confirm attribute,
            // if not we can return early and let the default behavior happen
            // This seems like a bug in HTMX, but it's the only way to handle the confirm dialog
            if (!event.detail.question) return

            event.preventDefault(); // Prevent the default confirm

            ckan.confirm({
                message: event.detail.question,
                type: "primary",
                centered: true,
                onConfirm: () => {
                    // If the user confirms, we manually issue the request
                    // true to skip the built-in window.confirm()
                    event.detail.issueRequest(true);
                }
            });
        },

        /**
         * Handle actions after HTMX content is swapped into the DOM
         *
         * This includes:
         * - Showing a success notification if the `hx-confirm-success` attribute is set
         *
         * @param {Event} event The HTMX afterSwap event
         */
        _onAfterSwap: function (event) {
            const successMsg = event.detail.requestConfig.elt.getAttribute("hx-confirm-success");

            if (successMsg) {
                ckan.toast({message: successMsg, type: "success"});
            }
        },
    };
});
