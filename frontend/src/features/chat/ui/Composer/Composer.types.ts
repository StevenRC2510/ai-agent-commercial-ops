export interface ComposerProps {
  disabled: boolean;
  lockedHint?: string;
  onSend: (text: string) => void;
}
