import type { UserRole } from "../../domain/roles.types";

// Named `value`, not `role`: a JSX attribute called role is read as an ARIA role.
export interface RoleSelectorProps {
  value: UserRole;
  disabled: boolean;
  onChange: (role: UserRole) => void;
}
