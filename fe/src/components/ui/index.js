/**
 * Central re-export for the design-system primitives.
 *
 * Components elsewhere in the app should always import from
 * `components/ui` (or the specific submodule) — never define one-off styled
 * buttons / inputs / cards. If you need a new pattern, add it here so it's
 * reusable and themed.
 */
export { Button, buttonVariants } from './button';
export { Input } from './input';
export { Label } from './label';
export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './card';
export { Badge, badgeVariants } from './badge';
export { Separator } from './separator';
export { Skeleton } from './skeleton';
export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from './dialog';
export { ScrollArea, ScrollBar } from './scroll-area';
export { Tabs, TabsList, TabsTrigger, TabsContent } from './tabs';
export { Switch } from './switch';
export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuRadioGroup,
} from './dropdown-menu';
