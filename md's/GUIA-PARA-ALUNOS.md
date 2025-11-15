# 📋 GUIA PARA OS ALUNOS - Como Aceitar o Pull Request e Configurar o Sistema

## 🎯 **RESUMO PARA A EQUIPE**

Este pull request corrige **2 bugs críticos** que impedem o sistema de funcionar:
1. **Face++ INVALID_OUTER_ID** (erro HTTP 400)
2. **Email Routes 404 Not Found**

**Status atual**: Sistema funcionando 100% no ambiente de desenvolvimento ✅

---

## 🚀 **PASSO A PASSO PARA ACEITAR E CONFIGURAR**

### **ETAPA 1: Aceitar o Pull Request**

1. **Acesse o GitHub**: https://github.com/JoseLeandroAC/Desafio-Makerthon/pulls
2. **Localize o PR**: `fix: Corrige bugs críticos Face++ INVALID_OUTER_ID e rotas de email 404`
3. **Revisar alterações**: 
   - Clique em "Files changed" para ver o que mudou
   - Principais: `app.py` e `.env`
4. **Aceitar**: Clique "Merge pull request" → "Confirm merge"

### **ETAPA 2: Atualizar o Código Local**

```bash
# 1. Ir para o diretório do projeto
cd caminho/para/Desafio-Makerthon

# 2. Garantir que está na branch main
git checkout main

# 3. Puxar as atualizações
git pull origin main

# 4. Verificar se as alterações chegaram
git log --oneline -5
```

### **ETAPA 3: 🔧 CONFIGURAR O BANCO DE DADOS (CRÍTICO)**

#### **A. Deletar Banco Atual (FORÇA)**
```sql
-- Conectar no PostgreSQL como superuser
psql -U postgres

-- Terminar todas as conexões com o banco
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity 
WHERE datname = 'alunossesi' AND pid <> pg_backend_pid();

-- Deletar o banco (FORÇA)
DROP DATABASE IF EXISTS alunossesi;

-- Verificar se foi deletado
\l
```

#### **B. Recriar o Banco do Zero**
```sql
-- Ainda no psql
CREATE DATABASE alunossesi 
    WITH OWNER = postgres 
    ENCODING = 'UTF8';

-- Verificar criação
\l

-- Sair do psql
\q
```

#### **C. Executar o Setup Atualizado**
```bash
# No diretório do projeto
python setup_db.py
```

**✅ Resultado esperado:**
```
Conexão bem-sucedida ao PostgreSQL!
Tabelas criadas/atualizadas com sucesso!
- Tabela 'alunos' com colunas: id, nome, face_token, data_cadastro, email_responsavel, turno
- Tabela 'presencas' com colunas: id, aluno_id, data_presenca, horario_presenca, presente, confianca
```

### **ETAPA 4: 📝 CONFIGURAR ARQUIVO .env**

#### **A. Localizar o arquivo `.env`**
```bash
# Verificar se existe
ls -la .env
```

#### **B. Editar com as configurações corretas**
```env
# CONFIGURAÇÕES DO BANCO (AJUSTAR CONFORME SEU AMBIENTE)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=alunossesi
DB_USER=postgres
DB_PASSWORD=1234                    # ⚠️ ALTERAR PARA SUA SENHA!

# CONFIGURAÇÕES FACE++ (USAR SUAS CREDENCIAIS)
FACE_API_KEY=sua_chave_face_aqui    # ⚠️ SUAS CREDENCIAIS!
FACE_API_SECRET=seu_secret_aqui     # ⚠️ SUAS CREDENCIAIS!
FACESET_ID=ChamadaAlunos

# CONFIGURAÇÕES GMAIL (USAR SUA CONTA)
GMAIL_USER=seu_email@gmail.com      # ⚠️ SEU EMAIL!
GMAIL_APP_PASSWORD=sua_senha_app    # ⚠️ SUA SENHA DE APP!
EMAIL_DELAY_SECONDS=1
EMAIL_SCHEDULE_HOUR=18
EMAIL_SCHEDULE_MINUTE=00
TIMEZONE=America/Sao_Paulo

# FLASK
FLASK_SECRET=troque-esta-chave-secreta
```

**🚨 IMPORTANTE**: 
- Substitua `DB_PASSWORD=1234` pela senha real do seu PostgreSQL
- Coloque suas credenciais reais da Face++ API
- Configure seu email Gmail com senha de app

### **ETAPA 5: 🧪 TESTAR O SISTEMA**

#### **A. Iniciar o Sistema**
```bash
# Instalar dependências (se necessário)
pip install -r requirements.txt

# Executar
python app.py
```

#### **B. Verificar Logs de Inicialização**
**✅ Logs esperados:**
```
🚀 Sistema iniciado!
- Interface: http://localhost:5000
- Admin: http://localhost:5000/admin
- API: http://localhost:5000/presencas
 * Running on http://127.0.0.1:5000
```

**❌ Se der erro de banco:**
```
Erro ao conectar ao banco: connection failed: FATAL: autenticação do tipo senha falhou
```
→ **Solução**: Verificar `DB_PASSWORD` no `.env`

#### **C. Testes Funcionais**

**1. Teste Face++ API:**
```bash
# Acessar: http://localhost:5000
# Clicar: "Fazer Chamada"
# Resultado esperado: "FaceSet vazio - Cadastre alunos primeiro" ✅
# NÃO deve dar: "INVALID_OUTER_ID" ❌
```

**2. Teste Email Routes:**
```bash
# Acessar: http://localhost:5000/admin
# Clicar nos botões:
# - 🌅 "Enviar (Manhã)" → deve funcionar ✅
# - 🌇 "Enviar (Tarde)" → deve funcionar ✅
# - 📧 "Enviar (Todos)" → deve funcionar ✅
# NÃO deve dar: "404 Not Found" ❌
```

### **ETAPA 6: 🔍 TROUBLESHOOTING**

#### **Erro 1: Face++ INVALID_OUTER_ID**
```bash
# Causa: Credenciais incorretas
# Solução: Verificar .env
grep FACE_API .env

# Deve mostrar:
# FACE_API_KEY=sua_chave_real
# FACE_API_SECRET=seu_secret_real
```

#### **Erro 2: Email Routes 404**
```bash
# Causa: Código não atualizado
# Solução: Verificar se pull request foi aplicado
grep -n "enviar_avisos_turno" app.py

# Deve encontrar a função na linha ~340
```

#### **Erro 3: Banco de Dados**
```bash
# Teste de conexão
python -c "
import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
try:
    conn = psycopg.connect(
        host=os.getenv('DB_HOST'),
        dbname=os.getenv('DB_NAME'), 
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    print('✅ Conexão OK!')
    conn.close()
except Exception as e:
    print(f'❌ Erro: {e}')
"
```

---

## 📊 **CHECKLIST DE VALIDAÇÃO**

Após seguir todos os passos, verificar:

- [ ] ✅ Pull request aceito e código atualizado
- [ ] ✅ Banco `alunossesi` deletado e recriado
- [ ] ✅ Arquivo `.env` configurado com suas credenciais
- [ ] ✅ `python setup_db.py` executado com sucesso
- [ ] ✅ `python app.py` inicia sem erros
- [ ] ✅ Face++ API retorna "FaceSet vazio" (não INVALID_OUTER_ID)
- [ ] ✅ Botões de email funcionam (não 404 Not Found)

---

## 🆘 **SUPORTE**

Se ainda houver problemas após seguir este guia:

1. **Verificar logs**: Copiar a mensagem de erro completa
2. **Verificar .env**: Garantir que credenciais estão corretas
3. **Testar conectividade**: Banco, Face++ API, Gmail
4. **Documentação**: Consultar arquivos `*-md` criados pelo PR

---

## 🎯 **RESULTADO FINAL ESPERADO**

**Antes do PR:**
- ❌ Face++ HTTP 400 INVALID_OUTER_ID
- ❌ Email buttons 404 Not Found
- ❌ Sistema não funciona

**Depois do PR + Configuração:**
- ✅ Face++ funcionando (reconhecimento facial OK)
- ✅ Sistema de emails por turno funcionando
- ✅ Interface admin 100% funcional
- ✅ Sistema completo operacional

---

**📅 Guia criado em**: 16 de Setembro de 2025  
**🎯 Status**: Testado e Funcionando  
**⚡ Prioridade**: CRÍTICA (sistema não funciona sem estas correções)

**💡 DICA FINAL**: Façam backup do `.env` atual antes de alterar, caso precisem reverter as configurações!