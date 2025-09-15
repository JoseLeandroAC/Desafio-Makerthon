# 📸 Sistema de Chamada por Reconhecimento Facial# Sistema de Chamada por Reconhecimento Facial# Sistema de Chamada por Reconhecimento Facial



Sistema automático para controle de presença usando sua webcam e inteligência artificial.



---Sistema de controle de presença usando reconhecimento facial com Face++ API e PostgreSQL.## 🚀 Como usar



## 📋 **PRÉ-REQUISITOS**



Antes de começar, você precisa ter instalado:## 🚀 Instalação### 1. Configurar banco PostgreSQL



### 1. **Python** (versão 3.8 ou superior)```bash

- **Windows**: Baixe em [python.org](https://python.org/downloads)

- **Durante a instalação**: ✅ Marque "Add Python to PATH"### 1. Instalar dependênciaspython setup_db.py

- **Teste**: Abra o CMD e digite `python --version`

```bash```

### 2. **PostgreSQL** (Banco de dados)

- **Windows**: Baixe em [postgresql.org](https://www.postgresql.org/downloads)# Criar ambiente virtual

- **Durante a instalação**: 

  - Anote a senha do usuário `postgres`python -m venv .venv### 2. Executar sistema

  - Porta padrão: `5432`

- **Teste**: Abra pgAdmin ou psql```bash



### 3. **Git** (para baixar o projeto)# Ativar ambiente virtualpython app.py

- **Windows**: Baixe em [git-scm.com](https://git-scm.com)

.venv\Scripts\activate  # Windows```

---

# source .venv/bin/activate  # Linux/Mac

## 🚀 **INSTALAÇÃO PASSO A PASSO**

### 3. Acessar

### **PASSO 1: Baixar o projeto**

```bash# Instalar dependências- **Sistema principal**: http://localhost:5000

# Abra o Prompt de Comando (CMD) ou PowerShell

# Navegue até onde quer salvar o projeto (ex: Desktop)pip install -r requirements.txt- **Painel admin**: http://localhost:5000/admin

cd C:\Users\SEU_USUARIO\Desktop

```- **API JSON**: http://localhost:5000/presencas

# Clone o projeto

git clone https://github.com/Carollaynef/tentativa2.git

cd tentativa2

```### 2. Configurar banco PostgreSQL## 📁 Estrutura



### **PASSO 2: Criar ambiente virtual**```bash```

```bash

# Crie um ambiente isolado para o projetopython setup_db.py├── app.py              # Sistema principal

python -m venv .venv

```├── setup_db.py         # Configuração do banco

# Ative o ambiente (Windows)

.venv\Scripts\activate├── .env                # Configurações do banco



# Você verá (.venv) no início da linha quando ativo### 3. Executar sistema├── alunos/             # Fotos dos alunos

```

```bash├── templates/

### **PASSO 3: Instalar dependências**

```bashpython app.py│   ├── index.html      # Interface principal

# Com o ambiente ativo, instale as bibliotecas

pip install -r requirements.txt```│   └── admin.html      # Painel administrativo



# Aguarde a instalação terminar (pode demorar uns 2-3 minutos)└── static/             # Arquivos estáticos

```

### 4. Acessar```

### **PASSO 4: Configurar o banco de dados**

```bash- **Sistema principal**: http://localhost:5000

# Execute o script de configuração

python setup_db.py- **Painel admin**: http://localhost:5000/admin## 🗄️ Banco PostgreSQL



# Se aparecer erro, verifique se PostgreSQL está rodando- **API JSON**: http://localhost:5000/presencas- **alunos**: id, nome, face_token, data_cadastro

```

- **presencas**: id, aluno_id, data_presenca, horario_presenca, presente, confianca

### **PASSO 5: Adicionar fotos dos alunos**

1. **Abra a pasta `alunos/`** no projeto## 📁 Estrutura do Projeto

2. **Adicione uma foto para cada aluno** com o nome do arquivo sendo o nome do aluno

   - ✅ **Correto**: `João Silva.jpg`, `Maria Santos.png````## ⚙️ Configuração (.env)

   - ❌ **Errado**: `foto1.jpg`, `imagem.png`

3. **Formato das fotos**:sistema-presenca/```

   - Tipos aceitos: `.jpg`, `.png`, `.jpeg`

   - Tamanho recomendado: até 2MB├── .venv/              # Ambiente virtual PythonDB_HOST=localhost

   - **Importante**: Foto deve mostrar o rosto claramente

├── alunos/             # Fotos dos alunosDB_PORT=5432

---

├── static/             # CSS, JS, imagensDB_NAME=presenca_alunos

## 🎮 **COMO USAR O SISTEMA**

├── templates/          # Templates HTMLDB_USER=postgres

### **PASSO 1: Iniciar o sistema**

```bash├── .env                # Configurações do bancoDB_PASSWORD=123456

# No terminal, execute:

python app.py├── app.py              # Aplicação principal Flask```



# Aguarde aparecer:├── setup_db.py         # Script de configuração do banco

# 🚀 Sistema iniciado!

# - Interface: http://localhost:5000├── requirements.txt    # Dependências Python## 🎯 Funcionalidades

# - Admin: http://localhost:5000/admin

# - API: http://localhost:5000/presencas├── alunos_tokens.json  # Cache dos tokens Face++1. **Cadastrar Alunos**: Registra fotos na Face++ e PostgreSQL

```

└── README.md           # Este arquivo2. **Fazer Chamada**: Detecta rosto e marca presença (1 por dia)

### **PASSO 2: Primeiro uso - Cadastrar alunos**

1. **Abra seu navegador** (Chrome, Firefox, Edge)```3. **Painel Admin**: Visualiza presenças do dia atual

2. **Digite**: `http://localhost:5000`

3. **Clique em "Cadastrar Alunos"** (botão azul)4. **API JSON**: Dados em formato JSON

4. **Aguarde**: O sistema vai processar todas as fotos da pasta `alunos/`## 🗄️ Banco de Dados PostgreSQL

5. **Resultado**: Você verá quantos alunos foram cadastrados- **alunos**: id, nome, face_token, data_cadastro

- **presencas**: id, aluno_id, data_presenca, horario_presenca, presente, confianca

### **PASSO 3: Fazer chamada (uso diário)**

1. **Acesse**: `http://localhost:5000`## ⚙️ Configuração (.env)

2. **Permita o uso da câmera** quando o navegador pedir```env

3. **Posicione seu rosto** na frente da câmeraDB_HOST=localhost

4. **Clique no botão da câmera** 📷DB_PORT=5432

5. **Aguarde o resultado**:DB_NAME=presenca_alunos

   - ✅ **"[Nome] está presente!"** = Presença registradaDB_USER=postgres

   - ⚠️ **"[Nome] já está presente hoje!"** = Você já fez chamada hojeDB_PASSWORD=123456

   - ❌ **"Não identificado"** = Rosto não reconhecidoFACE_API_KEY=seu_api_key_aqui

   - ❌ **"Nenhum rosto detectado"** = Posicione melhor na câmeraFACE_API_SECRET=seu_api_secret_aqui

```

### **PASSO 4: Ver relatório (professores/administradores)**

1. **Acesse**: `http://localhost:5000/admin`## 🎯 Funcionalidades

2. **Veja**: Lista de presenças do dia atual1. **Cadastrar Alunos**: Registra fotos na Face++ e PostgreSQL

3. **Informações mostradas**:2. **Fazer Chamada**: Detecta rosto e marca presença (máximo 1 por dia)

   - Nome do aluno3. **Painel Admin**: Visualiza presenças do dia atual

   - Status (Presente/Ausente)4. **API JSON**: Acesso aos dados em formato JSON

   - Horário da chamada

   - Nível de confiança da identificação## 🔧 Tecnologias Utilizadas

- **Backend**: Flask (Python)

---- **Banco de Dados**: PostgreSQL

- **Reconhecimento Facial**: Face++ API

## 🗓️ **FUNCIONAMENTO DIÁRIO**- **Frontend**: HTML, CSS, JavaScript

- **Webcam**: Navigator.mediaDevices API

### **Como funciona a presença:**

- ✅ **1ª tentativa do dia**: Registra presença normalmente## 📝 Como Usar

- ⚠️ **2ª tentativa do mesmo dia**: Mostra "já está presente"1. **Primeiro acesso**: Cadastre os alunos através do botão "Cadastrar Alunos"

- 🔄 **Próximo dia**: Pode registrar presença novamente2. **Fazer chamada**: Clique no botão da câmera para capturar e identificar

- 📊 **Histórico**: Cada dia fica salvo separadamente no banco3. **Ver presenças**: Acesse o painel admin para visualizar os registros

4. **API**: Use o endpoint JSON para integração com outros sistemas
### **Horários importantes:**
- **Início**: Sem limite de horário mínimo
- **Limite**: Sem limite de horário máximo
- **Cada dia**: Nova oportunidade de registrar presença

---

## 🔧 **RESOLUÇÃO DE PROBLEMAS**

### **❌ Erro: "Módulo não encontrado"**
```bash
# Certifique-se que o ambiente virtual está ativo
.venv\Scripts\activate

# Reinstale as dependências
pip install -r requirements.txt
```

### **❌ Erro: "Conexão com banco recusada"**
1. Verifique se PostgreSQL está rodando
2. Confirme usuário e senha no arquivo `.env`
3. Teste conexão: abra pgAdmin

### **❌ Erro: "Câmera não funciona"**
1. **Navegador**: Use Chrome ou Firefox (recomendado)
2. **HTTPS**: Se necessário, acesse via `https://localhost:5000`
3. **Permissões**: Verifique se permitiu acesso à câmera
4. **Antivírus**: Pode estar bloqueando a câmera

### **❌ Erro: "Aluno não reconhecido"**
1. **Foto**: Verifique se a foto está na pasta `alunos/`
2. **Nome do arquivo**: Deve ser exatamente o nome do aluno
3. **Qualidade**: Foto deve mostrar o rosto claramente
4. **Re-cadastrar**: Execute "Cadastrar Alunos" novamente

### **❌ Erro: "Face++ API"**
1. Verifique conexão com internet
2. Confirme chaves API no arquivo `.env`
3. Verifique se não excedeu limite de uso da API

---

## 📱 **DICAS DE USO**

### **Para melhor reconhecimento:**
- 💡 **Iluminação**: Use em local bem iluminado
- 👤 **Posicionamento**: Rosto centralizado na câmera
- 📏 **Distância**: Nem muito perto, nem muito longe
- 😐 **Expressão**: Mantenha expressão neutra
- 👓 **Óculos**: Pode usar, mas evite reflexos

### **Para administradores:**
- 📊 **Relatórios**: Acesse `/admin` para ver presenças
- 🔗 **API**: Use `/presencas` para dados em JSON
- 💾 **Backup**: Faça backup regular do banco PostgreSQL
- 🔄 **Atualizações**: Execute `git pull` para atualizações

---

## 📞 **SUPORTE**

### **Problemas técnicos:**
1. **Primeiro**: Tente reiniciar o sistema (`Ctrl+C` e `python app.py`)
2. **Logs**: Verifique mensagens no terminal
3. **Internet**: Confirme conexão estável
4. **Documentação**: Releia este README

### **Contato:**
- 📧 **Email**: [seu-email@exemplo.com]
- 💬 **Chat**: [link-do-chat]
- 📱 **WhatsApp**: [seu-numero]

---

## 📚 **ARQUIVOS IMPORTANTES**

```
📁 Projeto/
├── 📁 alunos/              ← COLOQUE AS FOTOS AQUI
├── 📁 templates/           ← Interface do sistema
├── 📁 static/              ← Estilos e imagens
├── 📄 app.py              ← Programa principal
├── 📄 setup_db.py         ← Configuração do banco
├── 📄 requirements.txt    ← Lista de dependências
├── 📄 .env               ← Configurações (senhas)
└── 📄 README.md          ← Este manual
```

**🎯 Lembre-se: O mais importante são as fotos na pasta `alunos/` com o nome correto!**

---

## ⚡ **RESUMO RÁPIDO**

### **Para começar:**
1. Instale Python e PostgreSQL
2. Clone o projeto: `git clone [url]`
3. Execute: `pip install -r requirements.txt`
4. Configure: `python setup_db.py`
5. Adicione fotos na pasta `alunos/`
6. Inicie: `python app.py`

### **Para usar diariamente:**
1. Acesse: `http://localhost:5000`
2. Clique na câmera 📷
3. Aguarde o resultado
4. Professor vê relatório em `/admin`

**✨ É só isso! Sistema pronto para uso!**