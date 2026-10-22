"""Plain-language definitions of every metric, shown in the app and the docs."""

METRICS = {
    "gross_sales": {
        "label": "Gross sales",
        "definition": "Sum of quantity × unit price over product sale lines.",
    },
    "returns": {
        "label": "Returns",
        "definition": (
            "Value of product cancellation/return lines (C-prefixed invoices in the UCI data), "
            "shown as a positive amount. Dated by the cancellation's own date."
        ),
    },
    "net_revenue": {
        "label": "Net revenue",
        "definition": (
            "Gross sales minus returns, for products only. Shipping, discounts, fees, "
            "manual adjustments, samples, gift vouchers and bad-debt entries are reported "
            "separately as other lines."
        ),
    },
    "orders": {
        "label": "Orders",
        "definition": "Number of distinct invoices containing at least one product sale line.",
    },
    "units": {
        "label": "Units sold",
        "definition": "Sum of quantities on product sale lines.",
    },
    "avg_order_value": {
        "label": "Average order value",
        "definition": "Gross sales divided by orders.",
    },
    "customers": {
        "label": "Identified customers",
        "definition": (
            "Distinct customer IDs on product sale lines. Lines without a customer ID count "
            "towards revenue but not towards this figure."
        ),
    },
}

NOT_AVAILABLE = (
    "Profit, margin and stock availability cannot be calculated: the data contains no cost "
    "or inventory information."
)
