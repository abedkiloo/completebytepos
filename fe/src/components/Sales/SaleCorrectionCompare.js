import React from 'react';
import { saleCorrectionCompareItems } from '../../utils/actionHelp';
import HelpHint from '../Shared/HelpHint';

export default function SaleCorrectionCompare({ highlight }) {
  const items = saleCorrectionCompareItems();
  return (
    <div className="space-y-2 rounded-md border bg-muted/40 p-3 text-xs">
      <p className="font-medium text-foreground">Choose the right correction</p>
      <ul className="space-y-2">
        {items.map((item) => {
          const active = highlight === item.key;
          return (
            <li
              key={item.key}
              className={
                active
                  ? 'rounded-md border border-amber-300 bg-amber-50/80 p-2 dark:border-amber-800 dark:bg-amber-950/40'
                  : 'rounded-md p-2'
              }
            >
              <div className="flex items-start gap-1">
                <span className="font-semibold text-foreground">{item.title}</span>
                <HelpHint actionKey={item.key} />
              </div>
              <p className="mt-1 text-muted-foreground">{item.body}</p>
              {item.contrast ? (
                <p className="mt-1 text-amber-800 dark:text-amber-200">{item.contrast}</p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
