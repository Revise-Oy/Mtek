# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
import ast


class ProductConfiguratorSale(models.TransientModel):

    _name = "product.configurator.sale"
    _inherit = "product.configurator"
    _description = "Product Configurator Sale"

    order_id = fields.Many2one(comodel_name="sale.order", required=True, readonly=True)
    order_line_id = fields.Many2one(comodel_name="sale.order.line", readonly=True)

    def _get_order_line_vals(self, product_id):
        """Hook to allow custom line values to be put on the newly
        created or edited lines."""
        product = self.env["product.product"].browse(product_id)
        line_vals = {"product_id": product_id, "order_id": self.order_id.id}
        extra_vals = self.order_line_id._prepare_add_missing_fields(line_vals)
        line_vals.update(extra_vals)

        # calculate new price
        total_price = 0
        if self.quantity:
            quantity = ast.literal_eval(self.quantity)
            attr_val_obj = self.env["product.attribute.value"]
            extra_prices = attr_val_obj.get_attribute_value_extra_prices(
                product_tmpl_id=self.product_tmpl_id.id, pt_attr_value_ids=self.value_ids
            )
            for attrib_val in self.value_ids:
                if quantity.get('__quantity-'+str(attrib_val.attribute_id.id)):
                    qty = quantity.get('__quantity-' + str(attrib_val.attribute_id.id))
                else:
                    qty = 1
                price_unit = self.product_tmpl_id.list_price + extra_prices.get(attrib_val.id)
                total_price += (price_unit * qty)
            line_vals['price_unit'] = total_price

        line_vals.update(
            {
                "config_session_id": self.config_session_id.id,
                "name": product._get_mako_tmpl_name(),
                "customer_lead": product.sale_delay,
            }
        )
        return line_vals

    def action_config_done(self):
        """Parse values and execute final code before closing the wizard"""
        res = super(ProductConfiguratorSale, self).action_config_done()
        if res.get("res_model") == self._name:
            return res
        model_name = "sale.order.line"
        line_vals = self._get_order_line_vals(res["res_id"])

        # Call onchange explicite as write and create
        # will not trigger onchange automatically
        order_line_obj = self.env[model_name]
        cfg_session = self.config_session_id
        specs = cfg_session.get_onchange_specifications(model=model_name)
        updates = order_line_obj.onchange(line_vals, ["product_id"], specs)
        values = updates.get("value", {})
        values = cfg_session.get_vals_to_write(values=values, model=model_name)
        values.update(line_vals)

        if self.order_line_id:
            self.order_line_id.write(values)
        else:
            self.order_id.write({"order_line": [(0, 0, values)]})
        return

    @api.model
    def create(self, vals):
        if self.env.context.get("default_order_line_id", False):
            sale_line = self.env["sale.order.line"].browse(
                self.env.context["default_order_line_id"]
            )
            if sale_line.custom_value_ids:
                vals["custom_value_ids"] = self._get_custom_values(
                    sale_line.config_session_id
                )
        res = super(ProductConfiguratorSale, self).create(vals)
        return res

    def _get_custom_values(self, session):
        custom_values = [(5,)] + [
            (
                0,
                0,
                {
                    "attribute_id": value_custom.attribute_id.id,
                    "value": value_custom.value,
                    "attachment_ids": [
                        (4, attach.id) for attach in value_custom.attachment_ids
                    ],
                },
            )
            for value_custom in session.custom_value_ids
        ]
        return custom_values