# Inventory reservation design

## Available and reserved stock
On-hand stock is the physical quantity in a warehouse. Reserved stock is promised to active orders. Available stock equals on hand minus reserved. A reservation must verify availability and create the hold inside one transaction.

## Transaction boundaries
Use an immediate SQLite write transaction to serialize competing reservations. Reject a request if there is insufficient available stock. Shipping a reservation reduces the on-hand quantity and closes the hold together. Releasing a reservation frees the hold without changing physical stock.

## Audit history
Record adjustments with a reason and keep a movement log. A negative adjustment must not reduce stock below the amount already reserved. Audit entries help explain why the current balance differs from yesterday.
