export {};

declare global {
  interface Window {
    forge?: {
      backendUrl?: string;
      setBadgeCount?: (count: number) => Promise<unknown>;
      notify?: (title: string, body: string, actionUrl?: string) => Promise<unknown>;
      onFileDropped?: (listener: (path: string) => void) => (() => void) | void;
    };
  }
}
