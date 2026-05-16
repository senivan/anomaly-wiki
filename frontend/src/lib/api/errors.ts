export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly body: unknown = {},
  ) {
    super(detail);
    this.name = "ApiError";
  }
}
