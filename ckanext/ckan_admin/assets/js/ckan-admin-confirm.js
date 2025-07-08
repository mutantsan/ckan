/**
 * CKAN Confirm Module
 *
 * Provides a reusable confirmation modal using Bootstrap 5, integrated into CKAN via `sandbox.publish`.
 *
 * Usage:
 * Trigger confirmation dialog with `ckan-admin:confirm` event and options.
 *
 * Example:
 * this.sandbox.publish("ckan-admin:confirm", {
 *   message: "Are you sure?",
 *   title: "Confirm Action",
 *   confirmText: "Yes, proceed",
 *   cancelText: "Cancel",
 *   type: "danger",
 *   icon: "<i class='fa fa-exclamation-triangle me-2'></i>",
 *   onConfirm: () => console.log("Confirmed"),
 *   onCancel: () => console.log("Cancelled")
 * });
 *
 * Options:
 * - message     (string)  [required] Message in modal body
 * - title       (string)  Optional.  Modal title
 * - icon        (string)  Optional.  HTML icon before title
 * - confirmText (string)  Optional.  Confirm button label
 * - cancelText  (string)  Optional.  Cancel button label
 * - type        (string)  Optional.  Style variant (primary, danger, etc.)
 * - centered    (boolean) Optional.  Vertically center the modal
 * - scrollable  (boolean) Optional.  Make modal scrollable
 * - fullscreen  (boolean) Optional.  Expand to fullscreen
 * - backdrop    (boolean) Optional.  Show backdrop
 * - keyboard    (boolean) Optional.  Allow ESC key to close modal
 * - onConfirm   (func)    Optional.  Callback on confirm
 * - onCancel    (func)    Optional.  Callback on cancel or close
 */

ckan.module("ckan-admin-confirm", function ($) {
  return {
    options: {},

    styles: {
      secondary: { btnClose: "btn-close-white", main: "bg-secondary text-white", confirm: "btn-secondary" },
      light: { btnClose: "", main: "bg-light text-dark", confirm: "btn-light" },
      dark: { btnClose: "btn-close-white", main: "bg-dark text-white", confirm: "btn-dark" },
      info: { btnClose: "btn-close-white", main: "bg-info text-white", confirm: "btn-info" },
      primary: { btnClose: "btn-close-white", main: "bg-primary text-white", confirm: "btn-primary" },
      success: { btnClose: "btn-close-white", main: "bg-success text-white", confirm: "btn-success" },
      warning: { btnClose: "btn-close-white", main: "bg-warning text-dark", confirm: "btn-warning" },
      danger: { btnClose: "btn-close-white", main: "bg-danger text-white", confirm: "btn-danger" },
      default: { btnClose: "", main: "", confirm: "btn-primary" }
    },

    selectors: {
      modalId: "ckan-confirm-modal",
      yesBtnId: "ckan-confirm-yes",
      cancelBtnId: "ckan-confirm-cancel"
    },

    initialize: function () {
      $.proxyAll(this, /_/);

      this.sandbox.subscribe("ckan-admin:confirm", this._onConfirm);
    },

    _onConfirm: function (options) {
      console.log(options);

      if (!options || !options.message) {
        console.error("Confirm: Missing required 'message' option.");
        return;
      }

      // Merge options with defaults
      const opts = Object.assign({
        title: ckan.i18n._("Please Confirm"),
        icon: "",
        confirmText: ckan.i18n._("Confirm"),
        cancelText: ckan.i18n._("Cancel"),
        type: "default",
        onConfirm: function () { },
        onCancel: function () { },
        centered: true,
        scrollable: true,
        fullscreen: false,
        backdrop: "static",
        keyboard: false
      }, options);

      // Remove any existing modal
      const existing = document.getElementById(this.selectors.modalId);
      if (existing) existing.remove();

      const style = this.styles[opts.type] || this.styles.default;

      const dialogClasses = [
        "modal-dialog",
        opts.centered && "modal-dialog-centered",
        opts.scrollable && "modal-dialog-scrollable",
        opts.fullscreen && "modal-fullscreen"
      ].filter(Boolean).join(" ");

      const modalHTML = `
                <div class="modal fade" id="${this.selectors.modalId}" tabindex="-1" aria-hidden="true">
                    <div class="${dialogClasses}">
                        <div class="modal-content">
                            <div class="modal-header ${style.main}">
                                ${opts.icon}
                                <h5 class="modal-title">${opts.title}</h5>
                                <button type="button" class="btn-close ${style.btnClose}" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <p>${opts.message}</p>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" id="${this.selectors.cancelBtnId}">${opts.cancelText}</button>
                                <button type="button" class="btn ${style.confirm}" id="${this.selectors.yesBtnId}">${opts.confirmText}</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

      const wrapper = document.createElement("div");
      wrapper.innerHTML = modalHTML.trim();
      const modalEl = wrapper.firstChild;
      document.body.appendChild(modalEl);

      const modal = new bootstrap.Modal(modalEl, {
        backdrop: opts.backdrop,
        keyboard: opts.keyboard
      });

      modal.show();

      // Confirm
      modalEl.querySelector(`#${this.selectors.yesBtnId}`).addEventListener("click", () => {
        modal.hide();
        opts.onConfirm();
      });

      // Cancel or close
      modalEl.querySelector(`#${this.selectors.cancelBtnId}`).addEventListener("click", () => {
        modal.hide();
        opts.onCancel();
      });

      modalEl.querySelector(".btn-close").addEventListener("click", () => {
        modal.hide();
        opts.onCancel();
      });

      modalEl.addEventListener("hidden.bs.modal", () => {
        modalEl.remove();
      });

      modalEl.addEventListener("shown.bs.modal", () => {
        modalEl.focus(); // Needed for ESC key to work
      });
    }
  };
});
