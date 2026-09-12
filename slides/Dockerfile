# 簡報：Slidev 建成靜態站 → nginx。掛在 /slides/ 底下（前端 nginx 反向代理），所以 build 時要帶 --base。
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npx slidev build --base /slides/ --out dist

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html/slides
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  location /slides/ { try_files $uri $uri/ /slides/index.html; }\n  location = / { return 302 /slides/; }\n  location ~* \\.(mp4|avif|png|jpg|woff2?)$ { expires 7d; add_header Cache-Control "public"; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
