# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models
import ast


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def create_get_bom(self, variant, product_tmpl_id=None, values=None):

        # default_type is set as 'product' when the user navigates
        # through menu item "Products". This conflicts
        # with the type for mrp.bom when mrpBom.onchange() is executed.
        ctx = self.env.context.copy()
        if ctx.get("default_type"):
            ctx.pop("default_type")
        self.env.context = ctx

        if values is None:
            values = {}
        if product_tmpl_id is None or variant.product_tmpl_id != product_tmpl_id:
            product_tmpl_id = variant.product_tmpl_id

        mrpBom = self.env["mrp.bom"]
        mrpBomLine = self.env["mrp.bom.line"]
        attr_products = variant.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id.product_id"
        )

        # Mapping product with attribute.
        custom_product_attrib = {}
        for attribute in variant.product_template_attribute_value_ids:
            vals = '__quantity-'+str(attribute.attribute_id.id)
            custom_product_attrib.update({attribute.product_attribute_value_id.product_id.id: vals})

        attr_values = variant.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id"
        )
        # existing_bom = self.env["mrp.bom"].search(
        #     [
        #         ("product_tmpl_id", "=", product_tmpl_id.id),
        #         ("product_id", "=", variant.id),
        #     ]
        # )
        # if existing_bom:
        #     return existing_bom[:1]

        parent_bom = self.env["mrp.bom"].search(
            [
                ("product_tmpl_id", "=", product_tmpl_id.id),
                ("product_id", "=", False),
            ],
            order="sequence asc",
            limit=1,
        )
        bom_lines = []
        value_ids = self.value_ids.product_id.ids

        quantity = False
        if self.quantity:
            quantity = ast.literal_eval(self.quantity)
        if not parent_bom:
            # If not Bom, then Cycle through attributes to add their
            # related products to the bom lines.
            for product in attr_products:
                vals = 1
                # check for the custom quantity.
                if custom_product_attrib.get(product.id) and quantity and quantity.get(custom_product_attrib.get(product.id)):
                    vals = quantity.get(custom_product_attrib.get(product.id))

                # for key, vals in quantity.items():
                bom_line_vals = {"product_id": product.id, "product_qty": vals}
                specs = self.get_onchange_specifications(model="mrp.bom.line")
                updates = mrpBomLine.onchange(
                    bom_line_vals, ["product_id", "product_qty"], specs
                )
                values = updates.get("value", {})
                values = self.get_vals_to_write(values=values, model="mrp.bom.line")
                values.update(bom_line_vals)
                bom_lines.append((0, 0, values))
        else:
            # If parent BOM is used, then look through Config Sets
            # on parent product's bom to add the products to the bom lines.
            for parent_bom_line in parent_bom.bom_line_ids:
                if parent_bom_line.config_set_id:
                    for config in parent_bom_line.config_set_id.configuration_ids:
                        # Add bom lines if config values are part of attr_values
                        if set(config.value_ids.ids).issubset(set(attr_values.ids)):
                            if parent_bom_line.bom_id.id == parent_bom.id:
                                parent_bom_line_vals = {
                                    "product_id": parent_bom_line.product_id.id,
                                    "product_qty": parent_bom_line.product_qty,
                                }
                                specs = self.get_onchange_specifications(
                                    model="mrp.bom.line"
                                )
                                updates = mrpBomLine.onchange(
                                    parent_bom_line_vals,
                                    ["product_id", "product_qty"],
                                    specs,
                                )
                                values = updates.get("value", {})
                                values = self.get_vals_to_write(
                                    values=values, model="mrp.bom.line"
                                )
                                values.update(parent_bom_line_vals)
                                bom_lines.append((0, 0, values))
                else:
                    parent_bom_line_vals = {
                        "product_id": parent_bom_line.product_id.id,
                        "product_qty": parent_bom_line.product_qty,
                    }
                    specs = self.get_onchange_specifications(model="mrp.bom.line")
                    updates = mrpBomLine.onchange(
                        parent_bom_line_vals, ["product_id", "product_qty"], specs
                    )
                    values2 = updates.get("value", {})
                    values2 = self.get_vals_to_write(
                        values=values, model="mrp.bom.line"
                    )
                    values2.update(parent_bom_line_vals)
                    bom_lines.append((0, 0, values2))
        if bom_lines:
            bom_values = {
                "product_tmpl_id": self.product_tmpl_id.id,
                "product_id": variant.id,
                "bom_line_ids": bom_lines,
            }
            specs = self.get_onchange_specifications(model="mrp.bom")
            updates = mrpBom.onchange(
                bom_values,
                ["product_id", "product_tmpl_id", "bom_line_ids"],
                specs,
            )
            values = updates.get("value", {})
            values = self.get_vals_to_write(values=values, model="mrp.bom")
            values.update(bom_values)
            mrp_bom_id = mrpBom.create(values)
            if mrp_bom_id and parent_bom:
                for operation_line in parent_bom.operation_ids:
                    operation_line.copy(default={"bom_id": mrp_bom_id.id})
            return mrp_bom_id
        return False

    def create_get_variant(self, value_ids=None, custom_vals=None):
        variant = super(ProductConfigSession, self).create_get_variant(
            value_ids=value_ids, custom_vals=custom_vals
        )
        self.create_get_bom(variant=variant, product_tmpl_id=self.product_tmpl_id)
        return variant
