# 前端：Vite 建靜態檔 → nginx 服務，並把 /api 反向代理到 backend（同源，不需 CORS）
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --engine-strict=false --no-audit --no-fund
COPY . .
# 空字串＝同源呼叫 /api（api.ts 用 ?? 判斷）；要指到別台後端就 --build-arg VITE_API_BASE_URL=http://host:8000
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
