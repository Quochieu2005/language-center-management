"use client";

import { App, message as staticMessage } from "antd";
import type { MessageInstance } from "antd/es/message/interface";
import { useEffect } from "react";

/**
 * `message` đúng theme: antd cảnh báo khi gọi `message.success(...)` tĩnh vì nó không đọc được ConfigProvider/App.
 * Các trang nhập `message` từ đây thay vì từ "antd"; MessageBridge (đặt trong <App>) gắn bản có context vào,
 * trước đó hoặc ngoài cây React thì dùng bản tĩnh.
 */
let current: MessageInstance | null = null;

export const message = new Proxy({} as MessageInstance, {
  get: (_target, key) => {
    const source = (current ?? staticMessage) as unknown as Record<PropertyKey, unknown>;
    const value = source[key];
    return typeof value === "function" ? value.bind(source) : value;
  },
});

export function MessageBridge() {
  const { message: contextual } = App.useApp();
  useEffect(() => {
    current = contextual;
    return () => {
      if (current === contextual) current = null;
    };
  }, [contextual]);
  return null;
}
