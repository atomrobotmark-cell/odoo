/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class WahaChatIframe extends Component {
    setup() {
        super.setup();
    }
}

WahaChatIframe.template = "whatsapp_waha_sender.WahaChatIframe";
WahaChatIframe.props = standardFieldProps;
WahaChatIframe.supportedTypes = ["char"];

registry.category("fields").add("waha_chat_iframe", WahaChatIframe);
