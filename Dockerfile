FROM node:20-alpine

# Робоча директорія всередині контейнера
WORKDIR /app

# Копіюємо package.json і package-lock.json (якщо є)
COPY package*.json ./

# Встановлюємо залежності
RUN npm install

# Копіюємо увесь проєкт
COPY . .

# Порт, на якому працює додаток
EXPOSE 3000

# Команда запуску
CMD ["npm", "start"]
