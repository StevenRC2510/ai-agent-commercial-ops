import { cn } from "@/shared/lib/cn";

import { ROLE_LABELS, USER_ROLES } from "../../domain/roles";

import {
  GROUP,
  LEGEND,
  RADIO,
  SEGMENT,
  SEGMENT_OFF,
  SEGMENT_ON,
  SEGMENT_WRAP,
} from "./RoleSelector.constants";
import type { RoleSelectorProps } from "./RoleSelector.types";

// Native radios, so arrow keys and screen readers work without reimplementing them.
export const RoleSelector = ({ value, disabled, onChange }: RoleSelectorProps) => (
  <fieldset className={GROUP} disabled={disabled}>
    <legend className="sr-only">{LEGEND}</legend>
    {USER_ROLES.map((role) => (
      <label key={role} className={SEGMENT_WRAP}>
        <input
          type="radio"
          name="chat-role"
          value={role}
          checked={value === role}
          onChange={() => onChange(role)}
          className={RADIO}
        />
        <span className={cn(SEGMENT, value === role ? SEGMENT_ON : SEGMENT_OFF)}>
          {ROLE_LABELS[role]}
        </span>
      </label>
    ))}
  </fieldset>
);
