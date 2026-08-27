import { cn } from "@/shared/lib/cn";
import { BUTTON_BASE, BUTTON_GHOST } from "@/shared/ui/buttonStyles";

import { RoleSelector } from "../RoleSelector";

import { BAR, BRAND_SLOT, CLEAR, CLEAR_LABEL, CLEAR_SHORT, CONTROLS } from "./ChatHeader.constants";
import type { ChatHeaderProps } from "./ChatHeader.types";

// The app's only chrome. `brand` is a slot so the feature never owns the product's identity.
export const ChatHeader = ({ brand, role, disabled, onRoleChange, onClear }: ChatHeaderProps) => (
  <header className={BAR}>
    <div className={BRAND_SLOT}>{brand}</div>
    <div className={CONTROLS}>
      <RoleSelector value={role} disabled={disabled} onChange={onRoleChange} />
      <button
        type="button"
        onClick={onClear}
        disabled={disabled}
        title={CLEAR_LABEL}
        className={cn(BUTTON_BASE, BUTTON_GHOST, CLEAR)}
      >
        <span className="sr-only sm:not-sr-only">{CLEAR_LABEL}</span>
        <span aria-hidden="true" className="sm:hidden">
          {CLEAR_SHORT}
        </span>
      </button>
    </div>
  </header>
);
