export interface ConfirmationCardProps {
  summary: string;
  isConfirming: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}
