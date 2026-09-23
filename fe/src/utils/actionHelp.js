/**
 * Hover / confirm help for actions that change money, stock, or records.
 * Short label is the button; hover + confirmBody educate before the person commits.
 */

export const ACTION_HELP = {
  sale_refund: {
    shortLabel: 'Void / refund',
    title: 'Void or refund a sale',
    hover:
      'Use this when a customer returns goods, or you need to reverse some or all of a real sale. You can refund the whole receipt or selected lines. The original sale stays on record.',
    confirmTitle: 'Confirm void / refund?',
    confirmBody:
      'This reverses stock, revenue, and customer balances for the quantities you chose. The original receipt is kept for audit — it is not deleted. Do not use this to undo a mistaken checkout; use Roll back instead.',
    contrast:
      'Not for a cashier mistake. Roll back is for duplicate or wrong-till sales.',
  },
  sale_rollback: {
    shortLabel: 'Roll back sale',
    title: 'Roll back a mistaken sale',
    hover:
      'Use this when the sale should never have been recorded — duplicate checkout, wrong till, or wrong customer. It always reverses the whole sale and needs admin approval.',
    confirmTitle: 'Submit sale rollback?',
    confirmBody:
      'The whole sale is queued for admin approval. Stock, money, and books reverse only after an admin approves. Super Admin can apply it immediately. Do not use this for a customer return; use Void / refund instead.',
    contrast:
      'Not for a customer return. Void / refund is for goods coming back.',
  },
  sale_backfill: {
    shortLabel: 'Record past sale',
    title: 'Enter a sale after the fact',
    hover:
      'Use this when a sale happened earlier (busy day, paper receipt) and you are entering it now. It waits for manager approval before stock and books change.',
    confirmTitle: 'Submit past sale?',
    confirmBody:
      'This past sale is sent for manager approval. Stock and accounts stay unchanged until it is approved.',
  },
  product_price: {
    shortLabel: 'Price change',
    title: 'Change a selling price',
    hover: 'Updates the catalog selling price after a manager approves. POS keeps the current price until then.',
    confirmTitle: 'Submit price change?',
    confirmBody: 'The live price stays the same until a manager approves this request.',
  },
  product_stock: {
    shortLabel: 'Stock change',
    title: 'Change stock on hand',
    hover: 'Updates how much is in stock after approval. Counts on the shelf do not change until a manager approves.',
    confirmTitle: 'Submit stock change?',
    confirmBody: 'On-hand quantity stays unchanged until a manager approves this request.',
  },
  stock_adjust: {
    shortLabel: 'Stock adjustment',
    title: 'Adjust stock',
    hover: 'Corrects a count (damage, recount, found stock). Needs a short reason and manager approval when maker-checker is on.',
    confirmTitle: 'Confirm stock adjustment?',
    confirmBody: 'This adjustment is saved or queued for approval. Use a clear reason so the checker can verify it.',
  },
  approve_change: {
    shortLabel: 'Approve',
    title: 'Approve this request',
    hover: 'Makes the requested change live. The person who submitted it is not asked again.',
    confirmTitle: 'Approve this change?',
    confirmBody: 'This applies the requested change now. It cannot be undone from this screen.',
  },
  reject_change: {
    shortLabel: 'Return to requester',
    title: 'Return this request',
    hover:
      'Does not apply the change. The person who asked is told in Daily notes, with your reason, so they can fix it and send it back.',
    confirmTitle: 'Return this request?',
    confirmBody:
      'Nothing goes live. The requester gets a Daily notes task with your reason and can send the request back for approval.',
  },
  expense: {
    shortLabel: 'Expense',
    title: 'Expense approval',
    hover: 'Spending that waits for a checker before it hits reports.',
    confirmTitle: 'Approve this expense?',
    confirmBody: 'This records the expense as approved and posts it to the books.',
  },
  income: {
    shortLabel: 'Income',
    title: 'Income approval',
    hover: 'Non-sales money in. It waits for a checker before it hits reports.',
    confirmTitle: 'Approve this income?',
    confirmBody: 'This records the income as approved and posts it to the books.',
  },
  default: {
    shortLabel: 'Confirm',
    title: 'Confirm this action',
    hover: 'Review the summary before you continue. This writes the change to the system.',
    confirmTitle: 'Confirm action?',
    confirmBody: 'Review the summary, then confirm. This saves the change to the system.',
  },
};

export function getActionHelp(key) {
  if (!key) return ACTION_HELP.default;
  return ACTION_HELP[key] || ACTION_HELP.default;
}

export function saleCorrectionCompareItems() {
  const refund = getActionHelp('sale_refund');
  const rollback = getActionHelp('sale_rollback');
  return [
    { key: 'sale_refund', title: refund.title, body: refund.hover, contrast: refund.contrast },
    { key: 'sale_rollback', title: rollback.title, body: rollback.hover, contrast: rollback.contrast },
  ];
}
