# RAM Manager Pro

Gerenciador Profissional de Memória RAM para Windows

## Descrição

O **RAM Manager Pro** é uma aplicação profissional desenvolvida em Python para monitoramento, diagnóstico e otimização de memória RAM em tempo real.

### Funcionalidades

- **📊 Monitoramento em Tempo Real**: Visualize o uso atual da RAM com atualizações automáticas a cada 2 segundos
- **🔍 Informações Detalhadas**: Total, disponível, usada, cache e memória swap
- **🧹 Limpeza Manual**: Libere memória não utilizada instantaneamente
- **🤖 Limpeza Automática**: Ative a limpeza automática quando o uso ultrapassar 80%
- **📋 Gerenciamento de Processos**: Visualize e encerre processos por consumo de RAM
- **🎨 Interface Moderna**: Design escuro profissional com CustomTkinter

## Instalação

1. Instale as dependências necessárias:
```bash
pip install -r requirements.txt
```

2. Execute o programa:
```bash
python ram_manager.py
```

## Requisitos

- Windows 10 ou superior
- Python 3.8 ou superior
- Permissões de administrador (recomendado para melhor otimização)

## Uso

1. **Monitoramento**: A interface mostra automaticamente o uso da RAM em tempo real
2. **Limpeza Manual**: Clique em "Limpar RAM Agora" para otimização imediata
3. **Limpeza Automática**: Ative o modo automático para limpeza quando necessário
4. **Gerenciar Processos**: Visualize processos que consomem mais RAM e encerre-os se necessário

## Como Funciona

O programa utiliza técnicas avançadas de otimização de memória:
- Libera páginas de trabalho não utilizadas (`EmptyWorkingSet`)
- Força coleta de lixo do Python
- Monitora processos e permite encerramento manual
- Otimização automática baseada em thresholds configuráveis

## Segurança

- O programa não afeta negativamente outros aplicativos
- A limpeza libera apenas memória não essencial
- Processos críticos do sistema são protegidos
- Interface intuitiva para evitar ações acidentais

## Licença

Uso pessoal e profissional. Desenvolvido para otimização de sistemas Windows.
