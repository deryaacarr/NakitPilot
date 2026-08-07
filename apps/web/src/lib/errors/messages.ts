import type { AppErrorKind } from "./types";

export const ERROR_TITLES: Record<AppErrorKind, string> = {
  unauthorized: "Oturum süresi doldu",
  forbidden: "Yetkiniz yok",
  not_found: "Kayıt bulunamadı",
  validation: "Form hatası",
  server: "Sistem hatası",
  network: "Bağlantı hatası",
};

export const ERROR_MESSAGES: Record<AppErrorKind, string> = {
  unauthorized: "Oturumunuz sona erdi. Lütfen tekrar giriş yapın.",
  forbidden: "Bu işlemi gerçekleştirmek için yetkiniz bulunmuyor.",
  not_found: "İstediğiniz kayıt bulunamadı veya silinmiş olabilir.",
  validation: "Lütfen formdaki hataları düzeltip tekrar deneyin.",
  server: "Beklenmeyen bir sistem hatası oluştu. Lütfen daha sonra tekrar deneyin.",
  network: "Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.",
};

export function kindFromStatus(status: number): AppErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 400 || status === 422) return "validation";
  if (status >= 500) return "server";
  if (status === 0) return "network";
  return "server";
}
