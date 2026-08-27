import type { ReactNode } from "react";

import type { UserRole } from "../../domain/roles.types";

export interface ChatHeaderProps {
  brand: ReactNode;
  role: UserRole;
  disabled: boolean;
  onRoleChange: (role: UserRole) => void;
  onClear: () => void;
}
