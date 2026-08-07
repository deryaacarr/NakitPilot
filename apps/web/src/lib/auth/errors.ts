export type LoginErrorCode =
  | "invalid_email"
  | "invalid_password"
  | "inactive_account"
  | "server_error"
  | "network_error"
  | "validation";

export type LoginErrorState = {
  code: LoginErrorCode;
  message: string;
};

const MESSAGES: Record<LoginErrorCode, string> = {
  invalid_email: "Bu e-posta ile kayıtlı bir kullanıcı bulunamadı.",
  invalid_password: "Şifre hatalı. Lütfen tekrar deneyin.",
  inactive_account: "Hesabınız pasif durumda. Yöneticinizle iletişime geçin.",
  server_error: "Sunucu hatası oluştu. Lütfen biraz sonra tekrar deneyin.",
  network_error: "Sunucuya bağlanılamadı. Bağlantınızı kontrol edin.",
  validation: "Lütfen e-posta ve şifrenizi kontrol edin.",
};

export function loginErrorMessage(code: LoginErrorCode): string {
  return MESSAGES[code];
}

export function mapLoginApiError(status: number, body: unknown): LoginErrorState {
  const codeFromBody = extractErrorCode(body);

  if (codeFromBody === "invalid_email") {
    return { code: "invalid_email", message: loginErrorMessage("invalid_email") };
  }
  if (codeFromBody === "invalid_password") {
    return { code: "invalid_password", message: loginErrorMessage("invalid_password") };
  }
  if (codeFromBody === "inactive_account") {
    return { code: "inactive_account", message: loginErrorMessage("inactive_account") };
  }

  if (status >= 500 || status === 0) {
    return { code: "server_error", message: loginErrorMessage("server_error") };
  }

  return { code: "server_error", message: loginErrorMessage("server_error") };
}

function extractErrorCode(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const record = body as Record<string, unknown>;

  if (typeof record.code === "string") return record.code;

  const detail = record.detail;
  if (detail && typeof detail === "object" && detail !== null) {
    const detailRecord = detail as Record<string, unknown>;
    if (typeof detailRecord.code === "string") return detailRecord.code;
  }

  return null;
}
