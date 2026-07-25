FROM node:20-alpine AS base
WORKDIR /code
COPY package.json package-lock.json* ./
RUN npm install

FROM base AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM base AS build
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY --from=build /code/dist /usr/share/nginx/html
EXPOSE 80
