import {
  TriangleAlert,
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  Building2,
  Car,
  Check,
  CircleCheck,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  CircleAlert,
  CircleHelp,
  Clock,
  Folder,
  Info,
  Landmark,
  Languages,
  Link,
  List,
  Loader,
  Lock,
  LogOut,
  Minus,
  Phone,
  Plus,
  Search,
  Share2,
  Upload,
  User,
  X,
  type LucideIcon,
} from "lucide-react";

import { useUi } from "./context";

/** One icon per meaning (DESIGN_RULES section 6). Names are meanings, not shapes. */
const ICONS = {
  back: ArrowLeft,
  case: Folder,
  person: User,
  phone: Phone,
  bank: Landmark,
  vehicle: Car,
  org: Building2,
  zoomIn: Plus,
  zoomOut: Minus,
  list: List,
  picture: Share2,
  alsoAppearsIn: Link,
  strong: CircleCheck,
  possible: TriangleAlert,
  restricted: Lock,
  confirm: Check,
  reject: X,
  help: CircleHelp,
  language: Languages,
  next: ChevronRight,
  open: ChevronDown,
  loading: Loader,
  info: Info,
  problem: CircleAlert,
  search: Search,
  upload: Upload,
  pending: Clock,
  signOut: LogOut,
  sortUp: ArrowUp,
  sortDown: ArrowDown,
  sortNone: ChevronsUpDown,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICONS;

/**
 * Decorative icon: always hidden from assistive technology because a visible label
 * sits beside it (section 6). 24px in the officer app, 20px in the admin panel.
 */
export function Icon({ name }: { name: IconName }) {
  const { app } = useUi();
  const Glyph = ICONS[name];
  return (
    <Glyph
      className="tx-icon"
      size={app === "admin" ? 20 : 24}
      strokeWidth={2}
      aria-hidden="true"
      focusable="false"
    />
  );
}
