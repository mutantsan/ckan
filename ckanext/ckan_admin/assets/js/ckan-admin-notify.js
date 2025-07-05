/**
 * CKAN Notify Module
 *
 * Provides a UI mechanism to display Bootstrap 5 toast notifications across the CKAN admin interface.
 *
 * Usage:
 * Trigger notifications by publishing the `ckan-admin:notify` event via the sandbox with an options object.
 *
 * Example:
 * this.sandbox.publish("ckan-admin:notify", {
 *     message: "Operation completed successfully",
 *     type: "success",           // Bootstrap color scheme: success, danger, info, etc.
 *     title: "Done",
 *     icon: "<i class='fa fa-check-circle me-2'></i>",
 *     subtitle: "Just now",
 *     delay: 5000,               // Auto-hide delay in ms (0 = no auto-hide)
 *     position: "bottom-right"   // Position key from the module's `positions` map
 * });
 *
 * Options:
 * - message   (string)  [required] The main message body of the toast.
 * - type      (string)  Optional.  Defines toast style, matches keys from `styles`. Default: "default".
 * - title     (string)  Optional.  Text shown in the toast header.
 * - icon      (string)  Optional.  HTML for an icon displayed before the title.
 * - subtitle  (string)  Optional.  Text shown in the header's small subtitle area.
 * - delay     (number)  Optional.  Time in milliseconds before auto-hide. Default: 3000.
 * - position  (string)  Optional.  Position key controlling toast placement. Default: "bottom-right".
 *
 * Notes:
 * - Positions and styles are configurable via module options.
 * - Stacking behavior (allow multiple simultaneous toasts) is controlled with `this.options.stacking`.
 */

ckan.module("ckan-admin-notify", function ($) {
    return {
        options: {
            stacking: true,
            toastContainer: "toast-container",
            positions: {
                'top-left': 'top-0 start-0 ms-1 mt-1',
                'top-center': 'top-0 start-50 translate-middle-x mt-1',
                'top-right': 'top-0 end-0 me-1 mt-1',
                'middle-left': 'top-50 start-0 translate-middle-y ms-1',
                'middle-center': 'top-50 start-50 translate-middle p-3',
                'middle-right': 'top-50 end-0 translate-middle-y me-1',
                'bottom-left': 'bottom-0 start-0 ms-1 mb-1',
                'bottom-center': 'bottom-0 start-50 translate-middle-x mb-1',
                'bottom-right': 'bottom-0 end-0 me-1 mb-1'
            },
            styles: {
                secondary: {
                    btnClose: 'btn-close-white',
                    main: 'text-white bg-secondary',
                    border: 'border-secondary',
                    progress: "bg-secondary"
                },
                light: {
                    btnClose: '',
                    main: 'text-dark bg-light border-bottom border-dark',
                    border: 'border-dark',
                    progress: "bg-dark"
                },
                white: {
                    btnClose: '',
                    main: 'text-dark bg-white border-bottom border-dark',
                    border: 'border-dark',
                    progress: "bg-dark"
                },
                dark: {
                    btnClose: 'btn-close-white',
                    main: 'text-white bg-dark',
                    border: 'border-dark',
                    progress: "bg-dark"
                },
                info: {
                    btnClose: 'btn-close-white',
                    main: 'text-white bg-info',
                    border: 'border-info',
                    progress: "bg-info"
                },
                primary: {
                    btnClose: 'btn-close-white',
                    main: 'text-white bg-primary',
                    border: 'border-primary',
                    progress: "bg-primary"
                },
                success: {
                    btnClose: 'btn-close-white',
                    main: 'text-white bg-success',
                    border: 'border-success',
                    progress: "bg-success"
                },
                warning: {
                    btnClose: 'btn-close-white',
                    main: 'text-white bg-warning',
                    border: 'border-warning',
                    progress: "bg-warning"
                },
                danger: {
                    btnClose: 'btn-close-white',
                    main: 'text-white bg-danger',
                    border: 'border-danger',
                    progress: "bg-danger"
                },
                default: {
                    btnClose: "",
                    main: "",
                    border: "",
                    progress: "bg-primary"
                }
            }
        },
        initialize: function () {
            $.proxyAll(this, /_/);

            this.count = 0;

            this.sandbox.subscribe("ckan-admin:notify", this._onNotify);
        },

        _createToastContainer: function (position) {
            let containerID = this._makeContainerID(position);
            let containerEl = document.querySelector(`#${containerID}`);

            if (containerEl) {
                return containerEl;
            }

            const wrapperEl = document.createElement('div');
            const positionClasses = this.options.positions[position] || this.options.positions["bottom-right"];

            wrapperEl.classList.add('position-relative');
            wrapperEl.setAttribute('aria-live', 'polite');
            wrapperEl.setAttribute('aria-atomic', 'true');
            wrapperEl.innerHTML = `<div id="${containerID}" class="toast-container position-fixed pb-1 ${positionClasses}"></div>`;

            document.body.appendChild(wrapperEl);

            return wrapperEl.querySelector(`#${containerID}`);
        },

        /**
         * Shows a toast message
         *
         * @param {Object} options - The toast options
         */
        _onNotify: function (options) {
            const toastOptions = {
                type: "default",
                title: "",
                icon: "",
                subtitle: "",
                delay: 3000,
                position: "bottom-right",
                showProgress: true,
                ...options
            };

            Object.assign(toastOptions, options);

            if (!toastOptions.message) {
                console.error("Notify. Toast message is missing message!");
                return;
            }

            const style = this.options.styles[toastOptions.type] || this.options.styles.default;
            let containerEl = this._createToastContainer(toastOptions.position);
            let toast = document.createElement('div');

            toast.setAttribute('id', `toast-${++this.count}`);
            toast.setAttribute('role', 'alert');
            toast.setAttribute('aria-live', 'assertive');
            toast.setAttribute('aria-atomic', 'true');
            toast.classList.add('toast', 'align-items-center');
            style.border && toast.classList.add(style.border);

            toast.innerHTML = `<div class="toast-header ${style.main}">
                    ${toastOptions.icon}
                    <strong class="me-auto">${toastOptions.title}</strong>
                    <small>${toastOptions.subtitle}</small>
                    <button type="button" class="btn-close ${style.btnClose}" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${toastOptions.message}
                </div>`;

            if (!this.options.stacking) {
                containerEl.querySelectorAll(".toast").forEach((toast) => {
                    toast.remove();
                });
            }

            containerEl.appendChild(toast);

            toast.addEventListener('hidden.bs.toast', function (e) {
                e.target.remove();
            });

            const hasDelay = typeof toastOptions.delay === 'number' && toastOptions.delay > 0;
            const opts = { autohide: hasDelay, delay: hasDelay ? toastOptions.delay : 0 };


                if (hasDelay && toastOptions.showProgress) {
                const progressEl = document.createElement('div');
                progressEl.classList.add('progress-bar-timer');
                progressEl.classList.add(style.progress);
                progressEl.style.animationDuration = `${toastOptions.delay / 1000}s`;
                toast.querySelector('.toast-body').appendChild(progressEl);
            }


            new bootstrap.Toast(toast, opts).show();
        },

        _makeContainerID: function (position) {
            return `${this.options.toastContainer}-${position}`;
        },
    };
});
