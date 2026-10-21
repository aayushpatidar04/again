function get_issue_products_for_visit(issue) {
    const products = [];
    const add_product = (row) => {
        const item_code = row.item_code || "";
        const serial_no = row.serial_no || "";
        if (!item_code && !serial_no) return;

        products.push({
            item_code,
            item_name: row.item_name || "",
            description: row.description || "",
            serial_no,
        });
    };

    add_product({
        item_code: issue.item_code,
        item_name: issue.item_name,
        description: issue.item_description,
        serial_no: issue.serial_no,
    });
    (issue.item_list || []).forEach(add_product);

    const serialized_items = new Set(
        products.filter((row) => row.serial_no).map((row) => row.item_code)
    );
    const seen = new Set();
    return products.filter((row) => {
        if (!row.serial_no && serialized_items.has(row.item_code)) return false;
        const key = row.serial_no ? `serial:${row.serial_no}` : `item:${row.item_code}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
}

async function populate_visit_products_from_issue(frm) {
    if (!frm.is_new()) return;

    const issue_name = (frm.doc.custom_linked_issues || [])
        .map((row) => row.issue)
        .find(Boolean);
    if (!issue_name || frm._issue_product_import_pending ||
        frm._issue_product_import_done_for === issue_name) {
        return;
    }

    frm._issue_product_import_pending = true;
    try {
        const issue = await frappe.db.get_doc("Issue", issue_name);
        if (!frm.is_new() ||
            !(frm.doc.custom_linked_issues || []).some((row) => row.issue === issue_name)) {
            return;
        }

        const products = get_issue_products_for_visit(issue);
        const selected_codes = new Set(
            (frm.doc.products || []).map((row) => row.item_code).filter(Boolean)
        );
        const purpose_keys = new Set(
            (frm.doc.purposes || []).map((row) =>
                row.serial_no ? `serial:${row.serial_no}` : `item:${row.item_code}`
            )
        );

        products.forEach((product) => {
            if (product.item_code && !selected_codes.has(product.item_code)) {
                const selected = frm.add_child("products");
                selected.item_code = product.item_code;
                selected.item_name = product.item_name;
                selected.serial_no = product.serial_no;
                selected_codes.add(product.item_code);
            }

            const key = product.serial_no
                ? `serial:${product.serial_no}`
                : `item:${product.item_code}`;
            if (!purpose_keys.has(key)) {
                const purpose = frm.add_child("purposes");
                purpose.item_code = product.item_code;
                purpose.item_name = product.item_name;
                purpose.description = product.description;
                purpose.serial_no = product.serial_no;
                purpose_keys.add(key);
            }
        });

        frm.refresh_field("products");
        frm.refresh_field("purposes");
        frm._issue_product_import_done_for = issue_name;
    } catch (error) {
        frappe.msgprint(__("Could not load the Issue products. Please try again."));
        console.error(error);
    } finally {
        frm._issue_product_import_pending = false;
    }
}

frappe.ui.form.on("Maintenance Visit", {
    onload: populate_visit_products_from_issue,
    refresh: populate_visit_products_from_issue,
});
