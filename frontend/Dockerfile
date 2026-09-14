FROM node:20-alpine AS builder

WORKDIR /app

ARG REACT_APP_API_BASE_URL=/api/v1
ARG REACT_APP_API_KEY=""
ARG REACT_APP_TENANT_ID=demo_tenant
ARG REACT_APP_HR_CURRENCY=LKR

ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
ENV REACT_APP_API_KEY=$REACT_APP_API_KEY
ENV REACT_APP_TENANT_ID=$REACT_APP_TENANT_ID
ENV REACT_APP_HR_CURRENCY=$REACT_APP_HR_CURRENCY

COPY package*.json ./
RUN npm ci --prefer-offline --no-audit

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
