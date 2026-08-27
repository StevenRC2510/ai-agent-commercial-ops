FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# node_modules and the working tree are copied in as root; vite dev needs to write
# a temp config bundle under /app at startup, so the node user needs ownership.
RUN chown -R node:node /app

USER node
EXPOSE 5173
CMD ["npm", "run", "dev"]
