export type JsonRequestBody = object;

export type ApiRequestBody = BodyInit | JsonRequestBody | null;

export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  baseURL?: string;
  body?: ApiRequestBody;
};
