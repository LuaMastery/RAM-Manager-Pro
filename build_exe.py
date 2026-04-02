#!/usr/bin/env python3
"""
Script para criar executável standalone do RAM Manager Pro
"""

import PyInstaller.__main__
import os
import sys

def build_executable():
    """Cria o executável do RAM Manager Pro"""
    
    print("🔨 Criando executável do RAM Manager Pro...")
    print("=" * 60)
    
    # Verificar se matplotlib está instalado
    try:
        import matplotlib
        print("✅ Matplotlib encontrado")
    except ImportError:
        print("❌ Matplotlib não encontrado. Instalando...")
        os.system("pip install matplotlib")
    
    # Obter path absoluto
    base_path = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(base_path, "ram_manager.py")
    
    if not os.path.exists(main_script):
        print(f"❌ Arquivo não encontrado: {main_script}")
        sys.exit(1)
    
    print(f"📁 Script principal: {main_script}")
    print(f"📁 Diretório base: {base_path}")
    
    # Argumentos do PyInstaller
    args = [
        main_script,
        '--onefile',           # Arquivo único
        '--noconsole',         # Sem console (GUI apenas)
        '--name', 'RAM-Manager-Pro',
        '--clean',             # Limpar cache
        '--noconfirm',         # Não perguntar confirmações
    ]
    
    # Adicionar data files (config.json, stats.json, etc.)
    args.extend([
        '--add-data', f'{base_path};.',
    ])
    
    # Hidden imports (bibliotecas que PyInstaller pode não detectar)
    hidden_imports = [
        'customtkinter',
        'PIL',
        'PIL._imagingtk',
        'PIL._tkinter_finder',
        'matplotlib',
        'matplotlib.backends.backend_tkagg',
        'psutil',
        'wmi',
        'pywin32',
    ]
    
    for imp in hidden_imports:
        args.extend(['--hidden-import', imp])
    
    print("\n📦 Configuração do PyInstaller:")
    print(f"   - Modo: onefile (executável único)")
    print(f"   - Console: oculto (apenas GUI)")
    print(f"   - Nome: RAM-Manager-Pro.exe")
    print(f"   - Hidden imports: {len(hidden_imports)}")
    
    print("\n⚙️  Iniciando build...")
    print("=" * 60)
    
    try:
        PyInstaller.__main__.run(args)
        
        print("\n" + "=" * 60)
        print("✅ Build concluído com sucesso!")
        print("=" * 60)
        
        # Mostrar local do executável
        dist_path = os.path.join(base_path, "dist", "RAM-Manager-Pro.exe")
        if os.path.exists(dist_path):
            size_mb = os.path.getsize(dist_path) / (1024 * 1024)
            print(f"\n📦 Executável criado:")
            print(f"   📍 Local: {dist_path}")
            print(f"   📊 Tamanho: {size_mb:.1f} MB")
            print(f"\n🚀 Pronto para distribuição!")
            print(f"   O usuário pode baixar e executar diretamente.")
        else:
            print(f"\n⚠️  Executável não encontrado em: {dist_path}")
            print(f"   Verifique a pasta 'dist/' no diretório do projeto.")
            
    except Exception as e:
        print(f"\n❌ Erro durante o build: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    build_executable()
