# Field loads

Feature: **sales → field_load** (`Field loads`).

A field load is the stock a field agent carries out of the shop. It is separate from a field order, which is a customer order packed for delivery.

Issuing the load removes those units from shop stock. A sale recorded on the load does not remove them again. When the agent returns, each product must balance: taken = sold + returned + missing. A manager accepts the count, and only then do the returned units go back on the shelf. Sending the count back does not move stock, and the agent cannot be issued a second load while the first is still open or waiting.

The load shows the money those sales should have brought in, as cash, M-Pesa, or customer credit. A field-load sale is paid in full by cash or M-Pesa, or it is put on the customer's credit. There is no split payment. The manager’s OK is about the goods. Unpaid amounts stay on the customer.

Missing for each product is taken − sold − returned. A pending load with a gap is shown as a shortage. The shop enters the physical count. The manager approves it or sends it back.

A field-load sale is not a field order. A field order is packed for a customer and removes shop stock. A field-load sale uses stock already on the load, is stored as `field_load`, and does not remove shop stock again. Both still count toward the agent’s commission. Reports keep them in separate totals so a load sale is not listed as a shop sale or a field order.

The phone app has the same book under **Field load** for anyone with `agents.field_load` while the feature is on. The open load is one screen of stock, with the sale and the return count on their own steps so the actions stay in reach on a small phone. An agent records a field-load sale and the shop counts the return. Accepting the count stays with a manager. The person the load is written for is an active sales employee from the staff roster, not only a Field Sales login.
