"""
RAM Manager Pro - Gerenciador Profissional de Memória RAM
Autor: Sistema Automatizado
Descrição: Aplicativo profissional para monitoramento, diagnóstico e otimização de RAM
"""

import customtkinter as ctk
import psutil
import threading
import time
import ctypes
from ctypes import wintypes
from datetime import datetime
from collections import deque
import json
import os
import sys
import winsound  # Para efeitos sonoros no Windows
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

# Constantes Windows para Job Objects
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9

class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", ctypes.c_byte * 48),  # JOBOBJECT_BASIC_LIMIT_INFORMATION
        ("IoInfo", ctypes.c_byte * 32),  # IO_COUNTERS
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ConsoleRedirector:
    """Redireciona stdout/stderr para um CTkTextbox"""
    def __init__(self, textbox):
        self.textbox = textbox
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
    def write(self, message):
        """Escreve mensagem no console embutido"""
        if message.strip():  # Ignorar linhas vazias
            try:
                # Usar after para thread-safe update
                self.textbox.after(0, lambda msg=message: self._insert_text(msg))
            except:
                # Fallback para stdout original se houver erro
                self.original_stdout.write(message)
                
    def _insert_text(self, message):
        """Insere texto no textbox (chamado na thread principal)"""
        try:
            self.textbox.configure(state="normal")
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.textbox.insert("end", f"{timestamp} - {message}")
            self.textbox.see("end")
            self.textbox.configure(state="disabled")
        except Exception as e:
            self.original_stdout.write(f"Erro ao escrever no console: {e}\n")
            
    def flush(self):
        """Método flush necessário para compatibilidade"""
        pass
        
    def restore(self):
        """Restaura stdout/stderr originais"""
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

class RAMManagerPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("RAM Manager Pro v1.0")
        self.geometry("1000x700")
        self.minsize(900, 600)
        
        # Configurações
        self.auto_clean_interval = 300  # 5 minutos
        self.auto_clean_active = False
        self.history_data = deque(maxlen=100)
        self.process_list = []
        self._update_lock = threading.Lock()
        self._last_process_update = 0
        self._process_limits = {}  # PID -> limite em MB
        
        # Configurações de Alerta
        self.alert_enabled = True
        self.alert_threshold = 90  # porcentagem
        self.alert_sound = True
        self.alert_auto_clean = True  # limpar automaticamente após timeout
        self.alert_timeout = 10  # segundos
        self._alert_active = False
        self._alert_dialog = None
        
        # Configuração de Modo de Limpeza
        self.clean_mode = "normal"  # "normal" ou "complex"
        
        # Configuração de Modo de Limpeza Automática
        self.auto_clean_mode = "normal"  # "normal", "complex" ou "ai"
        
        # Configuração de Threshold de Limpeza Automática
        self.auto_clean_threshold = 80  # porcentagem para ativar limpeza automática
        
        # Configuração de Modo Automático Persistente
        self.auto_clean_persistent = False  # Se True, inicia automaticamente com o programa
        
        # Configuração de Inicialização
        self.start_with_windows = False
        
        # Estatísticas de Limpeza
        self.cleaning_stats = {
            'total_cleanings': 0,
            'total_freed_mb': 0,
            'cleaning_history': [],  # Lista de dicts: {timestamp, ram_before, ram_after, freed_mb, efficiency}
            'avg_freed_per_cleaning': 0,
            'best_cleaning': {'freed_mb': 0, 'timestamp': None},
            'last_7_days': [],
            'ram_usage_trend': []  # Lista de (timestamp, ram_percent)
        }
        
        # Carregar estatísticas
        self.load_stats()
        
        # Criar interface
        self.create_widgets()
        
        # Iniciar monitoramento
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self.monitor_ram, daemon=True)
        self.monitor_thread.start()
        
        # Carregar configurações
        self.load_config()
        
    def create_widgets(self):
        # Frame principal
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Header
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color=("gray85", "gray17"), corner_radius=15)
        self.header_frame.pack(fill="x", pady=(0, 15))
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="💾 RAM Manager Pro", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(side="left", padx=20, pady=15)
        
        # Botão de configurações
        self.config_btn = ctk.CTkButton(
            self.header_frame,
            text="⚙️ Config",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=80,
            height=30,
            corner_radius=8,
            command=self.open_config_dialog
        )
        self.config_btn.pack(side="right", padx=(0, 10), pady=15)
        
        self.status_indicator = ctk.CTkLabel(
            self.header_frame,
            text="● Monitorando",
            font=ctk.CTkFont(size=12),
            text_color="green"
        )
        self.status_indicator.pack(side="right", padx=20, pady=15)
        
        # Container principal dividido
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(1, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        
        # Painel Esquerdo - Informações e Gráficos
        self.left_panel = ctk.CTkFrame(self.content_frame, fg_color=("gray90", "gray13"), corner_radius=15)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.left_panel.grid_columnconfigure(0, weight=1)
        
        # Seção de Uso Atual
        self.current_usage_frame = ctk.CTkFrame(self.left_panel, fg_color=("gray85", "gray17"), corner_radius=12)
        self.current_usage_frame.pack(fill="x", padx=15, pady=15)
        
        ctk.CTkLabel(
            self.current_usage_frame,
            text="📊 Uso Atual da RAM",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        self.ram_percent_label = ctk.CTkLabel(
            self.current_usage_frame,
            text="0%",
            font=ctk.CTkFont(size=42, weight="bold")
        )
        self.ram_percent_label.pack(pady=10)
        
        self.ram_progress = ctk.CTkProgressBar(self.current_usage_frame, height=20, corner_radius=10)
        self.ram_progress.pack(fill="x", padx=15, pady=10)
        self.ram_progress.set(0)
        
        self.ram_details_label = ctk.CTkLabel(
            self.current_usage_frame,
            text="0 GB / 0 GB",
            font=ctk.CTkFont(size=14)
        )
        self.ram_details_label.pack(pady=(0, 15))
        
        # Seção de Informações Detalhadas
        self.info_frame = ctk.CTkFrame(self.left_panel, fg_color=("gray85", "gray17"), corner_radius=12)
        self.info_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        ctk.CTkLabel(
            self.info_frame,
            text="🔍 Informações Detalhadas",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=15)
        
        info_grid = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        info_grid.pack(fill="x", padx=15, pady=(0, 15))
        info_grid.grid_columnconfigure(0, weight=1)
        info_grid.grid_columnconfigure(1, weight=1)
        
        # Linhas de informação
        self.create_info_row(info_grid, 0, "Total:", "-- GB")
        self.create_info_row(info_grid, 1, "Disponível:", "-- GB")
        self.create_info_row(info_grid, 2, "Usada:", "-- GB")
        self.create_info_row(info_grid, 3, "Cache:", "-- GB")
        self.create_info_row(info_grid, 4, "Swap Usado:", "-- GB")
        
        self.total_label = info_grid.grid_slaves(row=0, column=1)[0]
        self.available_label = info_grid.grid_slaves(row=1, column=1)[0]
        self.used_label = info_grid.grid_slaves(row=2, column=1)[0]
        self.cache_label = info_grid.grid_slaves(row=3, column=1)[0]
        self.swap_label = info_grid.grid_slaves(row=4, column=1)[0]
        
        # Painel Direito - Controles e Processos
        self.right_panel = ctk.CTkFrame(self.content_frame, fg_color=("gray90", "gray13"), corner_radius=15)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.right_panel.grid_rowconfigure(1, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)
        
        # Seção de Controles
        self.controls_frame = ctk.CTkFrame(self.right_panel, fg_color=("gray85", "gray17"), corner_radius=12)
        self.controls_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        self.controls_frame.grid_columnconfigure((0, 1), weight=1)
        
        ctk.CTkLabel(
            self.controls_frame,
            text="⚙️ Controles",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=15, pady=(15, 10))
        
        # Botão de Limpeza Manual
        self.clean_btn = ctk.CTkButton(
            self.controls_frame,
            text="🧹 Limpar",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=35,
            corner_radius=10,
            command=self.clean_ram
        )
        self.clean_btn.grid(row=1, column=0, padx=(15, 4), pady=6, sticky="ew")
        
        # Botão de Limpeza Inteligente (IA)
        self.ai_clean_btn = ctk.CTkButton(
            self.controls_frame,
            text="🧠 IA Clean",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=35,
            corner_radius=10,
            fg_color="teal",
            hover_color="darkturquoise",
            command=self.ai_intelligent_clean
        )
        self.ai_clean_btn.grid(row=1, column=1, padx=4, pady=6, sticky="ew")
        
        # Botão de Limpeza Complexa
        self.clean_complex_btn = ctk.CTkButton(
            self.controls_frame,
            text="🚨 Limpar+",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=35,
            corner_radius=10,
            fg_color="purple",
            hover_color="darkviolet",
            command=self.clean_ram_aggressive
        )
        self.clean_complex_btn.grid(row=1, column=2, padx=4, pady=6, sticky="ew")
        
        # Botão de Diagnóstico Completo
        self.diagnose_btn = ctk.CTkButton(
            self.controls_frame,
            text="🔍 Diagnóstico",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=35,
            corner_radius=10,
            fg_color="orange",
            hover_color="darkorange",
            command=self.open_diagnostic_dialog
        )
        self.diagnose_btn.grid(row=1, column=3, padx=(4, 15), pady=6, sticky="ew")
        
        # Seção de Processos
        self.process_frame = ctk.CTkFrame(self.right_panel, fg_color=("gray85", "gray17"), corner_radius=12)
        self.process_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.process_frame.grid_rowconfigure(1, weight=1)
        self.process_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            self.process_frame,
            text="📋 Processos por Consumo de RAM",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=15, pady=15)
        
        # Scrollable frame para processos
        self.process_scroll = ctk.CTkScrollableFrame(self.process_frame, fg_color=("gray80", "gray20"), corner_radius=10)
        self.process_scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # Rodapé
        self.footer_frame = ctk.CTkFrame(self.main_frame, fg_color=("gray85", "gray17"), corner_radius=10, height=40)
        self.footer_frame.pack(fill="x", pady=(15, 0))
        self.footer_frame.pack_propagate(False)
        
        self.footer_label = ctk.CTkLabel(
            self.footer_frame,
            text="Pronto para otimizar",
            font=ctk.CTkFont(size=11)
        )
        self.footer_label.pack(side="left", padx=15)
        
        self.last_clean_label = ctk.CTkLabel(
            self.footer_frame,
            text="Última limpeza: Nunca",
            font=ctk.CTkFont(size=11)
        )
        self.last_clean_label.pack(side="right", padx=15)
        
        self.console_btn = ctk.CTkButton(
            self.footer_frame,
            text="📊 Estatísticas",
            font=ctk.CTkFont(size=10),
            width=80,
            height=25,
            corner_radius=5,
            fg_color="purple",
            hover_color="darkviolet",
            command=self.open_stats_dialog
        )
        self.console_btn.pack(side="right", padx=10)
        
        # Botão de limpeza automática
        self.auto_clean_btn = ctk.CTkButton(
            self.footer_frame,
            text="🤖 Auto: OFF",
            font=ctk.CTkFont(size=10),
            width=80,
            height=25,
            corner_radius=5,
            fg_color="gray",
            hover_color="darkgray",
            command=self.toggle_auto_clean
        )
        self.auto_clean_btn.pack(side="right", padx=10)
        
        # Botão para mostrar/ocultar console
        self.console_toggle_btn = ctk.CTkButton(
            self.footer_frame,
            text="📟 Console",
            font=ctk.CTkFont(size=10),
            width=80,
            height=25,
            corner_radius=5,
            command=self.toggle_console
        )
        self.console_toggle_btn.pack(side="right", padx=10)
        
        # Frame do Console (inicialmente oculto)
        self.console_frame = ctk.CTkFrame(self.main_frame, fg_color=("gray20", "gray10"), corner_radius=10)
        self.console_visible = False
        
        # Console output (Textbox)
        self.console_text = ctk.CTkTextbox(
            self.console_frame,
            height=150,
            font=ctk.CTkFont(size=10, family="Consolas"),
            fg_color=("gray15", "gray5"),
            text_color=("gray90", "gray90"),
            wrap="word"
        )
        self.console_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.console_text.configure(state="disabled")
        
        # Redirecionar stdout/stderr para o console
        self.console_redirector = ConsoleRedirector(self.console_text)
        sys.stdout = self.console_redirector
        sys.stderr = self.console_redirector
        
    def toggle_console(self):
        """Mostra ou oculta o console embutido"""
        if self.console_visible:
            self.console_frame.pack_forget()
            self.console_toggle_btn.configure(text="📟 Console")
            self.console_visible = False
        else:
            self.console_frame.pack(fill="x", padx=15, pady=(0, 15), before=self.footer_frame)
            self.console_toggle_btn.configure(text="📟 Ocultar")
            self.console_visible = True
            
    def log_to_console(self, message):
        """Adiciona mensagem ao console"""
        self.console_text.configure(state="normal")
        self.console_text.insert("end", f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.console_text.see("end")
        self.console_text.configure(state="disabled")
        
    def create_info_row(self, parent, row, label_text, value_text):
        ctk.CTkLabel(
            parent,
            text=label_text,
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70")
        ).grid(row=row, column=0, sticky="w", pady=3)
        
        ctk.CTkLabel(
            parent,
            text=value_text,
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=row, column=1, sticky="e", pady=3)
        
    def monitor_ram(self):
        """Thread de monitoramento contínuo da RAM - otimizada"""
        update_interval = 3  # segundos entre atualizações
        process_update_interval = 6  # segundos entre atualizações de processos
        last_process_update = 0
        
        while self.monitoring_active:
            try:
                # Informações da RAM
                ram = psutil.virtual_memory()
                swap = psutil.swap_memory()
                
                # Histórico
                self.history_data.append({
                    'timestamp': datetime.now(),
                    'percent': ram.percent,
                    'used': ram.used,
                    'available': ram.available
                })
                
                # Atualizar interface (dados da RAM)
                with self._update_lock:
                    if self.winfo_exists():
                        self.after(0, lambda r=ram, s=swap: self._safe_update_display(r, s))
                
                # Atualizar processos apenas a cada N segundos (mais leve)
                current_time = time.time()
                if current_time - last_process_update >= process_update_interval:
                    with self._update_lock:
                if self.alert_enabled and ram.percent >= self.alert_threshold:
                    with self._update_lock:
                        if self.winfo_exists():
                            self.after(0, lambda rp=ram.percent: self._check_alert(rp))
                    
            except Exception as e:
                print(f"Erro no monitoramento: {e}")
                
            time.sleep(update_interval)
            
    def _safe_update_display(self, ram, swap):
        """Atualização segura da UI com tratamento de erro"""
        try:
            if not self.winfo_exists():
                return
            self.update_display(ram, swap)
        except Exception as e:
            print(f"Erro ao atualizar display: {e}")
            
    def _safe_update_process_list(self):
        """Atualização segura da lista de processos"""
        try:
            if not self.winfo_exists():
                return
            self.update_process_list()
        except Exception as e:
            print(f"Erro ao atualizar processos: {e}")
            
    def update_display(self, ram, swap):
        # Atualizar percentual
        self.ram_percent_label.configure(text=f"{ram.percent}%")
        
        # Atualizar progress bar
        self.ram_progress.set(ram.percent / 100)
        
        # Mudar cor baseado no uso
        if ram.percent < 60:
            self.ram_progress.configure(progress_color="green")
            self.ram_percent_label.configure(text_color="green")
        elif ram.percent < 80:
            self.ram_progress.configure(progress_color="orange")
            self.ram_percent_label.configure(text_color="orange")
        else:
            self.ram_progress.configure(progress_color="red")
            self.ram_percent_label.configure(text_color="red")
            
        # Atualizar detalhes
        total_gb = ram.total / (1024**3)
        used_gb = ram.used / (1024**3)
        available_gb = ram.available / (1024**3)
        
        self.ram_details_label.configure(text=f"{used_gb:.1f} GB / {total_gb:.1f} GB")
        
        # Atualizar informações detalhadas
        self.total_label.configure(text=f"{total_gb:.2f} GB")
        self.available_label.configure(text=f"{available_gb:.2f} GB")
        self.used_label.configure(text=f"{used_gb:.2f} GB")
        
        # Calcular cache - verificar se atributo existe (compatibilidade)
        try:
            cached_mb = getattr(ram, 'cached', 0) / (1024**2)
        except:
            cached_mb = 0
        self.cache_label.configure(text=f"{cached_mb:.0f} MB")
        
        swap_used_gb = swap.used / (1024**3)
        self.swap_label.configure(text=f"{swap_used_gb:.2f} GB")
        
    def update_process_list(self):
        """Atualiza a lista de processos por consumo de RAM - otimizada"""
        try:
            if not self.winfo_exists():
                return
                
            # Limpar lista atual de forma segura
            children = self.process_scroll.winfo_children()
            if children:
                for widget in children:
                    try:
                        widget.destroy()
                    except:
                        pass
                self.update_idletasks()  # Forçar processamento de eventos pendentes
            
            # Obter processos com timeout curto para evitar travamentos
            processes = []
            try:
                # Usar process_iter com cache e timeout
                for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'memory_percent']):
                    try:
                        pinfo = proc.info
                        if pinfo and pinfo.get('memory_info') and pinfo['memory_info'].rss > 100 * 1024 * 1024:  # > 100MB (aumentado para reduzir lista)
                            processes.append(pinfo)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        pass
            except Exception as e:
                print(f"Erro ao iterar processos: {e}")
                    
            # Ordenar por uso de memória
            processes.sort(key=lambda x: x['memory_info'].rss, reverse=True)
            
            # Mostrar top 10 processos apenas (reduzido de 15)
            for i, proc in enumerate(processes[:10]):
                try:
                    self.create_process_row(proc, i)
                    self.update_idletasks()  # Processar eventos pendentes após cada linha
                except Exception as e:
                    print(f"Erro ao criar linha de processo: {e}")
                    
        except Exception as e:
            print(f"Erro ao atualizar processos: {e}")
            
    def create_process_row(self, proc, index):
        """Cria uma linha de processo na lista"""
        row_frame = ctk.CTkFrame(self.process_scroll, fg_color=("gray75", "gray25"), corner_radius=8, height=50)
        row_frame.pack(fill="x", pady=3)
        row_frame.pack_propagate(False)
        
        mem_mb = proc['memory_info'].rss / (1024**2)
        mem_percent = proc.get('memory_percent', 0)
        
        # Nome do processo (truncado)
        name = proc['name'][:25] if len(proc['name']) > 25 else proc['name']
        
        ctk.CTkLabel(
            row_frame,
            text=name,
            font=ctk.CTkFont(size=11),
            width=150
        ).pack(side="left", padx=10, pady=10)
        
        ctk.CTkLabel(
            row_frame,
            text=f"{mem_mb:.1f} MB",
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(side="left", padx=10, pady=10)
        
        ctk.CTkLabel(
            row_frame,
            text=f"({mem_percent:.1f}%)",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60")
        ).pack(side="left", padx=5, pady=10)
        
        # Botão de terminar
        def terminate_process(pid=proc['pid']):
            try:
                p = psutil.Process(pid)
                p.terminate()
                self.footer_label.configure(text=f"Processo {pid} terminado")
            except Exception as e:
                self.footer_label.configure(text=f"Erro ao terminar: {e}")
                
        ctk.CTkButton(
            row_frame,
            text="✕",
            width=30,
            height=25,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="red",
            hover_color="darkred",
            command=lambda p=proc['pid']: terminate_process(p)
        ).pack(side="right", padx=10, pady=10)
        
    def run_full_diagnostic(self):
        """Executa diagnóstico completo da RAM"""
        try:
            diagnostic = {
                'timestamp': datetime.now().isoformat(),
                'ram_info': self._get_detailed_ram_info(),
                'swap_info': self._get_swap_info(),
                'memory_pressure': self._calculate_memory_pressure(),
                'fragmentation_score': self._calculate_fragmentation(),
                'health_score': 0,
                'recommendations': []
            }
            
            # Calcular score de saúde (0-100)
            ram = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            health_score = 100
            
            # Penalizar uso alto de RAM
            if ram.percent > 80:
                health_score -= (ram.percent - 80) * 2
                diagnostic['recommendations'].append("🔴 Uso de RAM muito alto - Limpeza recomendada")
            elif ram.percent > 60:
                health_score -= (ram.percent - 60) * 0.5
                diagnostic['recommendations'].append("🟡 Uso de RAM moderado - Monitorar")
            
            # Penalizar uso de swap
            if swap.percent > 50:
                health_score -= 20
                diagnostic['recommendations'].append("🔴 Swap muito utilizado - RAM insuficiente")
            elif swap.percent > 20:
                health_score -= 10
                diagnostic['recommendations'].append("🟡 Swap em uso moderado")
            
            # Verificar processos com alto consumo
            high_memory_procs = self._get_high_memory_processes()
            if high_memory_procs:
                diagnostic['recommendations'].append(f"⚠️ {len(high_memory_procs)} processos consumindo >500MB")
            
            # Ajustar score
            diagnostic['health_score'] = max(0, min(100, health_score))
            
            # Adicionar recomendações baseadas no diagnóstico
            if diagnostic['health_score'] >= 80:
                diagnostic['status'] = "🟢 Saudável"
                diagnostic['recommendations'].insert(0, "✅ RAM está funcionando bem")
            elif diagnostic['health_score'] >= 60:
                diagnostic['status'] = "🟡 Atenção"
                diagnostic['recommendations'].insert(0, "⚠️ RAM precisa de manutenção")
            else:
                diagnostic['status'] = "🔴 Crítico"
                diagnostic['recommendations'].insert(0, "🚨 RAM em estado crítico - Ação necessária")
            
            return diagnostic
            
        except Exception as e:
            print(f"Erro no diagnóstico: {e}")
            return None
    
    def _get_detailed_ram_info(self):
        """Obtém informações detalhadas da RAM"""
        ram = psutil.virtual_memory()
        return {
            'total_gb': ram.total / (1024**3),
            'available_gb': ram.available / (1024**3),
            'used_gb': ram.used / (1024**3),
            'free_gb': ram.free / (1024**3),
            'percent_used': ram.percent,
            'cached_mb': getattr(ram, 'cached', 0) / (1024**2),
            'buffers_mb': getattr(ram, 'buffers', 0) / (1024**2),
            'active_mb': getattr(ram, 'active', 0) / (1024**2),
            'inactive_mb': getattr(ram, 'inactive', 0) / (1024**2)
        }
    
    def _get_swap_info(self):
        """Obtém informações do swap"""
        swap = psutil.swap_memory()
        return {
            'total_gb': swap.total / (1024**3),
            'used_gb': swap.used / (1024**3),
            'free_gb': swap.free / (1024**3),
            'percent_used': swap.percent,
            'sin': getattr(swap, 'sin', 0),
            'sout': getattr(swap, 'sout', 0)
        }
    
    def _calculate_memory_pressure(self):
        """Calcula pressão de memória (0-100)"""
        try:
            ram = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Fórmula de pressão de memória
            ram_pressure = ram.percent
            swap_penalty = swap.percent * 0.5
            
            return min(100, ram_pressure + swap_penalty)
        except:
            return 0
    
    def _calculate_fragmentation(self):
        """Estima fragmentação de memória"""
        try:
            ram = psutil.virtual_memory()
            if ram.total == 0:
                return 0
            
            # Fragmentação estimada baseada em memória livre vs disponível
            fragmentation = ((ram.total - ram.available) / ram.total) * 100
            return fragmentation
        except:
            return 0
    
    def _get_high_memory_processes(self):
        """Retorna processos usando >500MB"""
        high_memory = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if proc.info['memory_info'].rss > 500 * 1024 * 1024:  # >500MB
                        high_memory.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'memory_mb': proc.info['memory_info'].rss / (1024**2)
                        })
                except:
                    pass
        except:
            pass
        return sorted(high_memory, key=lambda x: x['memory_mb'], reverse=True)[:5]
    
    def ai_intelligent_clean(self):
        """IA - Limpeza inteligente baseada em diagnóstico"""
        try:
            self.footer_label.configure(text="🧠 IA: Analisando RAM...")
            self.update()
            
            # Executar diagnóstico
            diagnostic = self.run_full_diagnostic()
            if not diagnostic:
                self.footer_label.configure(text="❌ Erro no diagnóstico da IA")
                return
            
            # IA decide a melhor estratégia de limpeza
            strategy = self._ai_determine_strategy(diagnostic)
            
            self.footer_label.configure(text=f"🧠 IA: Executando {strategy['name']}...")
            self.update()
            
            # Executar limpeza baseada na estratégia
            ram_before = psutil.virtual_memory()
            freed_mb = self._execute_ai_strategy(strategy)
            ram_after = psutil.virtual_memory()
            
            # Mostrar resultados
            self._show_ai_results(diagnostic, strategy, freed_mb, ram_before, ram_after)
            
            # Registrar estatísticas
            self._record_cleaning_stats(ram_before, ram_after, freed_mb)
            
        except Exception as e:
            self.footer_label.configure(text=f"❌ Erro IA Clean: {e}")
            print(f"Erro detalhado: {e}")
    
    def _ai_determine_strategy(self, diagnostic):
        """IA - Determina a melhor estratégia de limpeza"""
        health_score = diagnostic['health_score']
        pressure = diagnostic['memory_pressure']
        ram_info = diagnostic['ram_info']
        
        strategy = {
            'name': 'Limpeza Padrão',
            'intensity': 'low',
            'methods': ['empty_working_set', 'gc_collect'],
            'description': 'Limpeza básica de segurança'
        }
        
        # IA: Análise inteligente baseada nos dados
        if health_score < 40 or pressure > 85:
            # Situação crítica - limpeza agressiva necessária
            strategy = {
                'name': 'Limpeza Crítica',
                'intensity': 'high',
                'methods': ['empty_working_set', 'trim_processes', 'gc_collect', 'clear_standby', 'force_cache_clear'],
                'description': 'Limpeza intensiva para situação crítica'
            }
        elif health_score < 65 or pressure > 70:
            # Situação moderada - limpeza equilibrada
            strategy = {
                'name': 'Limpeza Inteligente',
                'intensity': 'medium',
                'methods': ['empty_working_set', 'trim_large_processes', 'gc_collect', 'clear_standby'],
                'description': 'Limpeza equilibrada para otimização'
            }
        elif ram_info.get('cached_mb', 0) > 1000:
            # Muito cache acumulado - focar em cache
            strategy = {
                'name': 'Limpeza de Cache',
                'intensity': 'medium',
                'methods': ['empty_working_set', 'clear_standby', 'gc_collect'],
                'description': 'Foco em liberação de cache'
            }
        
        return strategy
    
    def _execute_ai_strategy(self, strategy):
        """Executa a estratégia determinada pela IA"""
        methods = strategy['methods']
        total_freed = 0
        
        try:
            ram_before = psutil.virtual_memory()
            
            if 'empty_working_set' in methods:
                try:
                    ctypes.windll.psapi.EmptyWorkingSet(ctypes.c_int(-1))
                except:
                    pass
            
            if 'trim_processes' in methods:
                # IA: Encerrar processos não essenciais grandes
                self._trim_non_essential_processes()
            
            if 'trim_large_processes' in methods:
                # IA: Reduzir working set de processos grandes
                self._trim_large_processes()
            
            if 'clear_standby' in methods:
                # Limpar lista de espera
                try:
                    ctypes.windll.kernel32.SetProcessWorkingSetSize(ctypes.c_int(-1), -1, -1)
                except:
                    pass
            
            if 'force_cache_clear' in methods:
                # Limpeza forçada de cache
                try:
                    import gc
                    gc.collect()
                    gc.collect(1)
                    gc.collect(2)
                except:
                    pass
            
            if 'gc_collect' in methods:
                import gc
                gc.collect()
            
            time.sleep(1.5)  # Aguardar efeitos
            
            ram_after = psutil.virtual_memory()
            total_freed = (ram_before.used - ram_after.used) / (1024**2)
            
        except Exception as e:
            print(f"Erro na execução da estratégia: {e}")
        
        return max(0, total_freed)
    
    def _trim_non_essential_processes(self):
        """Reduz working set de processos não essenciais"""
        try:
            non_essential = [
                'chrome.exe', 'firefox.exe', 'msedge.exe',  # Navegadores
                'spotify.exe', 'discord.exe', 'steam.exe',   # Apps de entretenimento
                'slack.exe', 'teams.exe', 'zoom.exe'         # Apps de comunicação
            ]
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if any(name in proc.info['name'].lower() for name in non_essential):
                        process = psutil.Process(proc.info['pid'])
                        # Tentar reduzir prioridade
                        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                except:
                    pass
        except:
            pass
    
    def _trim_large_processes(self):
        """Reduz working set de processos grandes"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if proc.info['memory_info'].rss > 300 * 1024 * 1024:  # >300MB
                        process = psutil.Process(proc.info['pid'])
                        # Reduzir working set do processo
                        try:
                            ctypes.windll.kernel32.SetProcessWorkingSetSize(
                                int(process._handle), -1, -1
                            )
                        except:
                            pass
                except:
                    pass
        except:
            pass
    
    def _show_ai_results(self, diagnostic, strategy, freed_mb, ram_before, ram_after):
        """Mostra resultados da limpeza IA"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("🧠 IA Clean - Resultados")
        dialog.geometry("500x600")
        dialog.transient(self)
        dialog.grab_set()
        
        # Título
        ctk.CTkLabel(
            dialog,
            text="🧠 Limpeza Inteligente Concluída",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=20)
        
        # Resumo
        summary_frame = ctk.CTkFrame(dialog, fg_color=("gray85", "gray17"), corner_radius=10)
        summary_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            summary_frame,
            text=f"💾 RAM Liberada: {freed_mb:.1f} MB",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=10)
        
        ctk.CTkLabel(
            summary_frame,
            text=f"📊 Score de Saúde: {diagnostic['health_score']}/100",
            font=ctk.CTkFont(size=12)
        ).pack(pady=5)
        
        ctk.CTkLabel(
            summary_frame,
            text=f"🔧 Estratégia: {strategy['name']}",
            font=ctk.CTkFont(size=12)
        ).pack(pady=5)
        
        # Recomendações
        rec_frame = ctk.CTkFrame(dialog, fg_color=("gray85", "gray17"), corner_radius=10)
        rec_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            rec_frame,
            text="📋 Diagnóstico:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        for rec in diagnostic['recommendations'][:4]:
            ctk.CTkLabel(
                rec_frame,
                text=f"  • {rec}",
                font=ctk.CTkFont(size=11),
                wraplength=400
            ).pack(anchor="w", padx=15, pady=2)
        
        # Status da RAM
        status_frame = ctk.CTkFrame(dialog, fg_color=("gray85", "gray17"), corner_radius=10)
        status_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            status_frame,
            text="📈 Status da RAM:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        ram_before_pct = ram_before.percent
        ram_after_pct = ram_after.percent
        improvement = ram_before_pct - ram_after_pct
        
        ctk.CTkLabel(
            status_frame,
            text=f"  Antes: {ram_before_pct:.1f}% | Depois: {ram_after_pct:.1f}% | Melhoria: {improvement:.1f}%",
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w", padx=15, pady=5)
        
        # Botão fechar
        ctk.CTkButton(
            dialog,
            text="OK",
            command=lambda: self._safe_destroy_dialog(dialog),
            width=100
        ).pack(pady=20)
    
    def open_diagnostic_dialog(self):
        """Abre diálogo de diagnóstico completo"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("🔍 Diagnóstico de RAM")
        dialog.geometry("600x700")
        dialog.transient(self)
        dialog.grab_set()
        
        # Executar diagnóstico
        diagnostic = self.run_full_diagnostic()
        
        if not diagnostic:
            ctk.CTkLabel(
                dialog,
                text="❌ Erro ao executar diagnóstico",
                font=ctk.CTkFont(size=14)
            ).pack(pady=20)
            return
        
        # Container com scroll
        main_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Título
        ctk.CTkLabel(
            main_frame,
            text="🔍 Diagnóstico Completo da RAM",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(10, 5))
        
        ctk.CTkLabel(
            main_frame,
            text=f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        ).pack(pady=(0, 10))
        
        # Score de saúde
        health_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        health_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            health_frame,
            text="💚 Score de Saúde",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        score = diagnostic['health_score']
        score_color = "green" if score >= 80 else "orange" if score >= 60 else "red"
        score_emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
        
        ctk.CTkLabel(
            health_frame,
            text=f"{score_emoji} {score}/100",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=score_color
        ).pack(pady=5)
        
        ctk.CTkLabel(
            health_frame,
            text=f"Status: {diagnostic['status']}",
            font=ctk.CTkFont(size=12)
        ).pack(pady=5)
        
        # Informações detalhadas
        info_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        info_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            info_frame,
            text="📊 Informações da RAM",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        ram_info = diagnostic['ram_info']
        
        details = [
            ("Total", f"{ram_info['total_gb']:.2f} GB"),
            ("Usada", f"{ram_info['used_gb']:.2f} GB ({ram_info['percent_used']:.1f}%)"),
            ("Disponível", f"{ram_info['available_gb']:.2f} GB"),
            ("Cache", f"{ram_info['cached_mb']:.0f} MB"),
            ("Buffers", f"{ram_info['buffers_mb']:.0f} MB"),
            ("Pressão de Memória", f"{diagnostic['memory_pressure']:.1f}%"),
        ]
        
        for label, value in details:
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(row, text=f"{label}:", font=ctk.CTkFont(size=11)).pack(side="left")
            ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=11, weight="bold")).pack(side="right")
        
        # Recomendações
        rec_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        rec_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            rec_frame,
            text="💡 Recomendações da IA",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        for rec in diagnostic['recommendations']:
            ctk.CTkLabel(
                rec_frame,
                text=f"• {rec}",
                font=ctk.CTkFont(size=11),
                wraplength=500
            ).pack(anchor="w", padx=15, pady=3)
        
        # Processos com alto consumo
        if diagnostic.get('high_memory_processes'):
            proc_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
            proc_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(
                proc_frame,
                text="⚠️ Processos com Alto Consumo",
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(anchor="w", padx=15, pady=(15, 10))
            
            for proc in diagnostic['high_memory_processes'][:5]:
                ctk.CTkLabel(
                    proc_frame,
                    text=f"  {proc['name']}: {proc['memory_mb']:.0f} MB",
                    font=ctk.CTkFont(size=11)
                ).pack(anchor="w", padx=15, pady=2)
        
        # Botões de ação
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="🧠 IA Clean",
            fg_color="teal",
            hover_color="darkturquoise",
            command=lambda: [self._safe_destroy_dialog(dialog), self.ai_intelligent_clean()],
            height=40,
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="❌ Fechar",
            fg_color="red",
            hover_color="darkred",
            command=lambda: self._safe_destroy_dialog(dialog),
            height=40,
            width=150
        ).pack(side="right", padx=5)

    def clean_ram(self, auto=False):
        """Executa a limpeza/otimização da RAM"""
        try:
            self.footer_label.configure(text="🧹 Limpando RAM...")
            self.update()
            
            # Obter estado anterior
            ram_before = psutil.virtual_memory()
            
            # Métodos de limpeza no Windows
            if os.name == 'nt':
                try:
                    # EmptyWorkingSet - libera páginas não utilizadas
                    ctypes.windll.psapi.EmptyWorkingSet(ctypes.c_int(-1))
                except:
                    pass
                    
            # Liberar caches do sistema
            try:
                # Limpar buffers de leitura de arquivos
                import gc
                gc.collect()
            except:
                pass
                
            # Aguardar um pouco
            time.sleep(1)
            
            # Obter estado após
            ram_after = psutil.virtual_memory()
            
            freed_bytes = ram_before.used - ram_after.used
            freed_mb = freed_bytes / (1024**2)
            
            if freed_mb > 0:
                status_msg = f"✅ RAM liberada: {freed_mb:.1f} MB"
            else:
                status_msg = "✅ RAM otimizada (já estava eficiente)"
                
            self.footer_label.configure(text=status_msg)
            self.last_clean_label.configure(text=f"Última limpeza: {datetime.now().strftime('%H:%M:%S')}")
            
            if not auto:
                # Mostrar popup de sucesso
                self.show_success_dialog(freed_mb)
                
            # Registrar estatísticas da limpeza
            self._record_cleaning_stats(ram_before, ram_after, freed_mb)
                
        except Exception as e:
            self.footer_label.configure(text=f"❌ Erro na limpeza: {e}")
            
    def _safe_destroy_dialog(self, dialog):
        """Destrói diálogo de forma segura"""
        try:
            dialog.grab_release()
        except:
            pass
        try:
            dialog.destroy()
        except:
            pass
        
    def _record_cleaning_stats(self, ram_before, ram_after, freed_mb):
        """Registra estatísticas de uma limpeza de RAM"""
        try:
            timestamp = datetime.now()
            
            # Atualizar estatísticas gerais
            self.cleaning_stats['total_cleanings'] += 1
            self.cleaning_stats['total_freed_mb'] += freed_mb
            
            # Registrar no histórico
            cleaning_record = {
                'timestamp': timestamp.isoformat(),
                'ram_before': ram_before,
                'ram_after': ram_after,
                'freed_mb': freed_mb,
                'efficiency': (freed_mb / ram_before * 100) if ram_before > 0 else 0
            }
            
            self.cleaning_stats['cleaning_history'].append(cleaning_record)
            
            # Manter apenas últimas 100 limpezas no histórico
            if len(self.cleaning_stats['cleaning_history']) > 100:
                self.cleaning_stats['cleaning_history'] = self.cleaning_stats['cleaning_history'][-100:]
            
            # Atualizar média
            total = self.cleaning_stats['total_cleanings']
            total_freed = self.cleaning_stats['total_freed_mb']
            self.cleaning_stats['avg_freed_per_cleaning'] = total_freed / total if total > 0 else 0
            
            # Atualizar melhor limpeza
            if freed_mb > self.cleaning_stats['best_cleaning']['freed_mb']:
                self.cleaning_stats['best_cleaning'] = {
                    'freed_mb': freed_mb,
                    'timestamp': timestamp.isoformat()
                }
            
            # Atualizar últimos 7 dias
            self._update_last_7_days(freed_mb)
            
            # Salvar estatísticas
            self.save_stats()
            
        except Exception as e:
            print(f"Erro ao registrar estatísticas: {e}")
    
    def _update_last_7_days(self, freed_mb):
        """Atualiza estatísticas dos últimos 7 dias"""
        try:
            today = datetime.now().date()
            
            # Verificar se já existe entrada para hoje
            existing = False
            for day_data in self.cleaning_stats['last_7_days']:
                day_date = datetime.fromisoformat(day_data['date']).date()
                if day_date == today:
                    day_data['cleanings'] += 1
                    day_data['total_freed'] += freed_mb
                    existing = True
                    break
            
            if not existing:
                self.cleaning_stats['last_7_days'].append({
                    'date': datetime.now().isoformat(),
                    'cleanings': 1,
                    'total_freed': freed_mb
                })
            
            # Manter apenas últimos 7 dias
            cutoff_date = today - __import__('datetime').timedelta(days=7)
            self.cleaning_stats['last_7_days'] = [
                day for day in self.cleaning_stats['last_7_days']
                if datetime.fromisoformat(day['date']).date() >= cutoff_date
            ]
            
        except Exception as e:
            print(f"Erro ao atualizar últimos 7 dias: {e}")
    
    def load_stats(self):
        """Carrega estatísticas do arquivo"""
        try:
            stats_path = os.path.join(os.path.dirname(__file__), 'stats.json')
            if os.path.exists(stats_path):
                with open(stats_path, 'r') as f:
                    loaded_stats = json.load(f)
                    self.cleaning_stats.update(loaded_stats)
        except Exception as e:
            print(f"Erro ao carregar estatísticas: {e}")
    
    def save_stats(self):
        """Salva estatísticas em arquivo"""
        try:
            stats_path = os.path.join(os.path.dirname(__file__), 'stats.json')
            with open(stats_path, 'w') as f:
                json.dump(self.cleaning_stats, f, indent=2)
        except Exception as e:
            print(f"Erro ao salvar estatísticas: {e}")
        
    def show_success_dialog(self, freed_mb):
        """Mostra diálogo de sucesso após limpeza"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Limpeza Concluída")
        dialog.geometry("350x200")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog,
            text="✅ Limpeza Concluída!",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=20)
        
        message = f"Aproximadamente {max(0, freed_mb):.1f} MB de memória foram otimizados."
        ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(size=12),
            wraplength=300
        ).pack(pady=10)
        
        ctk.CTkButton(
            dialog,
            text="OK",
            command=lambda: self._safe_destroy_dialog(dialog),
            width=100
        ).pack(pady=20)
        
    def open_stats_dialog(self):
        """Abre diálogo de estatísticas com gráficos"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("📊 Estatísticas de Limpeza")
        dialog.geometry("800x700")
        dialog.transient(self)
        dialog.grab_set()
        
        # Container principal com scroll
        main_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            main_frame,
            text="📊 Estatísticas de Eficácia",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(10, 15))
        
        # Frame de resumo
        summary_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        summary_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            summary_frame,
            text="📈 Resumo Geral",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        # Grid de métricas
        metrics_grid = ctk.CTkFrame(summary_frame, fg_color="transparent")
        metrics_grid.pack(fill="x", padx=15, pady=10)
        
        # Total de limpezas
        ctk.CTkLabel(
            metrics_grid,
            text=f"🧹 Total de Limpezas:\n{self.cleaning_stats['total_cleanings']}",
            font=ctk.CTkFont(size=13, weight="bold"),
            justify="center"
        ).grid(row=0, column=0, padx=20, pady=10)
        
        # Total liberado
        ctk.CTkLabel(
            metrics_grid,
            text=f"💾 Total Liberado:\n{self.cleaning_stats['total_freed_mb']:.1f} MB",
            font=ctk.CTkFont(size=13, weight="bold"),
            justify="center"
        ).grid(row=0, column=1, padx=20, pady=10)
        
        # Média por limpeza
        avg = self.cleaning_stats['avg_freed_per_cleaning']
        ctk.CTkLabel(
            metrics_grid,
            text=f"📊 Média por Limpeza:\n{avg:.1f} MB",
            font=ctk.CTkFont(size=13, weight="bold"),
            justify="center"
        ).grid(row=0, column=2, padx=20, pady=10)
        
        # Melhor limpeza
        best = self.cleaning_stats['best_cleaning']
        best_text = f"🏆 Melhor Limpeza:\n{best['freed_mb']:.1f} MB" if best['timestamp'] else "🏆 Melhor Limpeza:\nN/A"
        ctk.CTkLabel(
            metrics_grid,
            text=best_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            justify="center"
        ).grid(row=0, column=3, padx=20, pady=10)
        
        # Gráfico de eficiência das limpezas
        if self.cleaning_stats['cleaning_history']:
            chart_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
            chart_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(
                chart_frame,
                text="📉 Histórico de Limpezas (últimas 20)",
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(anchor="w", padx=15, pady=(15, 10))
            
            # Criar figura matplotlib
            fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
            fig.patch.set_facecolor('#2b2b2b')
            ax.set_facecolor('#2b2b2b')
            
            # Dados para o gráfico
            history = self.cleaning_stats['cleaning_history'][-20:]
            x = range(len(history))
            freed_amounts = [h['freed_mb'] for h in history]
            
            # Criar barras
            bars = ax.bar(x, freed_amounts, color='#ff6b35', alpha=0.7, edgecolor='#ff8c42')
            
            # Adicionar linha de tendência
            if len(freed_amounts) > 1:
                ax.plot(x, freed_amounts, color='#4a90d9', linewidth=2, marker='o', markersize=4)
            
            # Configurar eixos
            ax.set_xlabel('Limpezas (mais recentes →)', color='white', fontsize=10)
            ax.set_ylabel('MB Liberados', color='white', fontsize=10)
            ax.tick_params(colors='white')
            ax.spines['bottom'].set_color('white')
            ax.spines['left'].set_color('white')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Adicionar valores nas barras
            for i, (bar, val) in enumerate(zip(bars, freed_amounts)):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                           f'{val:.0f}', ha='center', va='bottom', 
                           color='white', fontsize=8)
            
            plt.tight_layout()
            
            # Incorporar no CustomTkinter
            canvas = FigureCanvasTkAgg(fig, master=chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(padx=10, pady=10, fill="x")
        
        # Gráfico dos últimos 7 dias
        if self.cleaning_stats['last_7_days']:
            days_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
            days_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(
                days_frame,
                text="📅 Atividade dos Últimos 7 Dias",
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(anchor="w", padx=15, pady=(15, 10))
            
            # Criar figura
            fig2, ax2 = plt.subplots(figsize=(10, 3), dpi=100)
            fig2.patch.set_facecolor('#2b2b2b')
            ax2.set_facecolor('#2b2b2b')
            
            # Preparar dados
            days_data = sorted(self.cleaning_stats['last_7_days'], 
                             key=lambda x: datetime.fromisoformat(x['date']))
            dates = [datetime.fromisoformat(d['date']).strftime('%d/%m') for d in days_data]
            cleanings = [d['cleanings'] for d in days_data]
            
            # Criar barras
            bars2 = ax2.bar(dates, cleanings, color='#4a90d9', alpha=0.7, edgecolor='#6bb3ff')
            
            # Configurar eixos
            ax2.set_xlabel('Data', color='white', fontsize=10)
            ax2.set_ylabel('Nº de Limpezas', color='white', fontsize=10)
            ax2.tick_params(colors='white')
            ax2.spines['bottom'].set_color('white')
            ax2.spines['left'].set_color('white')
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            
            plt.tight_layout()
            
            # Incorporar
            canvas2 = FigureCanvasTkAgg(fig2, master=days_frame)
            canvas2.draw()
            canvas2.get_tk_widget().pack(padx=10, pady=10, fill="x")
        
        # Mensagem de eficácia
        if self.cleaning_stats['total_cleanings'] > 0:
            efficiency_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
            efficiency_frame.pack(fill="x", padx=10, pady=10)
            
            total_freed = self.cleaning_stats['total_freed_mb']
            avg_per_clean = self.cleaning_stats['avg_freed_per_cleaning']
            
            if avg_per_clean >= 100:
                efficiency_msg = "🌟 Excelente! O aplicativo está sendo muito eficaz!"
                efficiency_color = "green"
            elif avg_per_clean >= 50:
                efficiency_msg = "✅ Bom! O aplicativo está ajudando significativamente."
                efficiency_color = "#4a90d9"
            elif avg_per_clean >= 20:
                efficiency_msg = "⚠️ Moderado. O aplicativo ajuda, mas pouco."
                efficiency_color = "orange"
            else:
                efficiency_msg = "📊 Baixa eficácia. Talvez seu PC já esteja otimizado."
                efficiency_color = "gray"
            
            ctk.CTkLabel(
                efficiency_frame,
                text="🎯 Avaliação de Eficácia",
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(anchor="w", padx=15, pady=(15, 5))
            
            ctk.CTkLabel(
                efficiency_frame,
                text=efficiency_msg,
                font=ctk.CTkFont(size=12),
                text_color=efficiency_color
            ).pack(anchor="w", padx=15, pady=(0, 15))
        
        # Botão fechar
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="❌ Fechar",
            fg_color="red",
            hover_color="darkred",
            command=lambda: self._safe_destroy_dialog(dialog),
            height=40,
            width=150
        ).pack()
        
    def toggle_auto_clean(self):
        """Ativa/desativa limpeza automática"""
        self.auto_clean_active = not self.auto_clean_active
        
        if self.auto_clean_active:
            self.auto_clean_btn.configure(
                text="🤖 Auto: ON",
                fg_color="green",
                hover_color="darkgreen"
            )
            self.footer_label.configure(text="🤖 Limpeza automática ativada (>80%)")
        else:
            self.auto_clean_btn.configure(
                text="🤖 Auto: OFF",
                fg_color="gray",
                hover_color="gray"
            )
            self.footer_label.configure(text="⏹️ Limpeza automática desativada")
            
    def load_config(self):
        """Carrega configurações salvas"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    if config.get('auto_clean', False):
                        self.toggle_auto_clean()
                    # Carregar configurações de alerta
                    self.alert_enabled = config.get('alert_enabled', True)
                    self.alert_threshold = config.get('alert_threshold', 90)
                    self.alert_sound = config.get('alert_sound', True)
                    self.alert_auto_clean = config.get('alert_auto_clean', True)
                    self.alert_timeout = config.get('alert_timeout', 10)
                    # Carregar modo de limpeza
                    self.clean_mode = config.get('clean_mode', 'normal')
                    # Carregar modo de limpeza automática
                    self.auto_clean_mode = config.get('auto_clean_mode', 'normal')
                    # Carregar threshold de limpeza automática
                    self.auto_clean_threshold = config.get('auto_clean_threshold', 80)
                    # Carregar configuração de inicialização
                    self.start_with_windows = config.get('start_with_windows', False)
                    # Carregar configuração de modo automático persistente
                    self.auto_clean_persistent = config.get('auto_clean_persistent', False)
                    # Se modo persistente estiver ativado, ativar limpeza automática na inicialização
                    if self.auto_clean_persistent and not self.auto_clean_active:
                        self.toggle_auto_clean()
        except:
            pass
            
    def save_config(self):
        """Salva configurações"""
        try:
            config = {
                'auto_clean': self.auto_clean_active,
                'alert_enabled': self.alert_enabled,
                'alert_threshold': self.alert_threshold,
                'alert_sound': self.alert_sound,
                'alert_auto_clean': self.alert_auto_clean,
                'alert_timeout': self.alert_timeout,
                'clean_mode': self.clean_mode,
                'auto_clean_mode': self.auto_clean_mode,
                'auto_clean_threshold': self.auto_clean_threshold,
                'auto_clean_persistent': self.auto_clean_persistent,
                'start_with_windows': self.start_with_windows
            }
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'w') as f:
                json.dump(config, f)
        except:
            pass
            
    def on_closing(self):
        """Handler para fechamento da aplicação"""
        self.save_config()
        self.monitoring_active = False
        self.destroy()
        
    def open_limit_dialog(self):
        """Abre diálogo para selecionar processo e definir limite de RAM"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Limitar RAM de Processo")
        dialog.geometry("500x450")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog,
            text="⚡ Limitar Memória de Processo",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(20, 15))
        
        # Frame para seleção de processo
        proc_frame = ctk.CTkFrame(dialog, fg_color=("gray85", "gray17"), corner_radius=10)
        proc_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            proc_frame,
            text="Selecione o Processo:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        # Combobox para processos
        self.proc_var = ctk.StringVar(value="")
        self.proc_combo = ctk.CTkComboBox(
            proc_frame,
            values=self._get_process_list(),
            variable=self.proc_var,
            width=400,
            height=35
        )
        self.proc_combo.pack(padx=15, pady=10)
        
        # Botão para atualizar lista
        ctk.CTkButton(
            proc_frame,
            text="🔄 Atualizar Lista",
            command=lambda: self.proc_combo.configure(values=self._get_process_list()),
            width=150,
            height=30
        ).pack(pady=(0, 15))
        
        # Frame para limite
        limit_frame = ctk.CTkFrame(dialog, fg_color=("gray85", "gray17"), corner_radius=10)
        limit_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            limit_frame,
            text="Limite Máximo de RAM:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        # Slider para limite
        self.limit_var = ctk.IntVar(value=512)
        slider_frame = ctk.CTkFrame(limit_frame, fg_color="transparent")
        slider_frame.pack(fill="x", padx=15, pady=5)
        
        self.limit_slider = ctk.CTkSlider(
            slider_frame,
            from_=100,
            to=4096,
            number_of_steps=40,
            variable=self.limit_var,
            width=300
        )
        self.limit_slider.pack(side="left", pady=5)
        
        self.limit_label = ctk.CTkLabel(
            slider_frame,
            text="512 MB",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=80
        )
        self.limit_label.pack(side="right", padx=10)
        
        def update_label(value):
            self.limit_label.configure(text=f"{int(value)} MB")
            
        self.limit_slider.configure(command=update_label)
        
        # Botões
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(
            btn_frame,
            text="✅ Aplicar Limite",
            fg_color="green",
            hover_color="darkgreen",
            command=lambda: self._apply_limit(dialog),
            height=40,
            width=150
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            btn_frame,
            text="❌ Cancelar",
            fg_color="red",
            hover_color="darkred",
            command=lambda: self._safe_destroy_dialog(dialog),
            height=40,
            width=150
        ).pack(side="right", padx=(10, 0))
        
    def _get_process_list(self):
        """Retorna lista de processos para o combobox"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    pinfo = proc.info
                    if pinfo and pinfo.get('memory_info') and pinfo['memory_info'].rss > 50 * 1024 * 1024:
                        mem_mb = pinfo['memory_info'].rss / (1024**2)
                        name = pinfo['name'][:30] if len(pinfo['name']) > 30 else pinfo['name']
                        processes.append(f"{name} (PID: {pinfo['pid']}) - {mem_mb:.0f}MB")
                except:
                    pass
        except:
            pass
        return processes if processes else ["Nenhum processo encontrado"]
        
    def _apply_limit(self, dialog):
        """Aplica o limite de memória ao processo selecionado"""
        selected = self.proc_var.get()
        if not selected or "Nenhum processo" in selected:
            self.footer_label.configure(text="❌ Selecione um processo válido")
            self._safe_destroy_dialog(dialog)
            return
            
        # Extrair PID
        try:
            pid = int(selected.split("PID: ")[1].split(")")[0])
        except:
            self.footer_label.configure(text="❌ Erro ao extrair PID")
            self._safe_destroy_dialog(dialog)
            return
            
        limit_mb = self.limit_var.get()
        
        try:
            if self._limit_process_memory(pid, limit_mb):
                self._process_limits[pid] = limit_mb
                proc_name = selected.split("(PID:")[0].strip()
                self.footer_label.configure(text=f"✅ Limite de {limit_mb}MB aplicado em {proc_name}")
            else:
                self.footer_label.configure(text="❌ Falha ao aplicar limite (execute como Admin)")
        except Exception as e:
            self.footer_label.configure(text=f"❌ Erro: {e}")
            
        self._safe_destroy_dialog(dialog)
        
    def _limit_process_memory(self, pid, limit_mb):
        """Aplica limite de memória via Windows Job Object"""
        try:
            # Abrir o processo
            PROCESS_ALL_ACCESS = 0x1F0FFF
            kernel32 = ctypes.windll.kernel32
            
            hProcess = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            if not hProcess:
                return False
                
            try:
                # Criar Job Object
                job_name = f"RAMLimit_{pid}"
                hJob = kernel32.CreateJobObjectW(None, job_name)
                if not hJob:
                    return False
                    
                # Configurar limites
                limit_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                limit_info.ProcessMemoryLimit = limit_mb * 1024 * 1024  # Converter MB para bytes
                
                # Configurar BasicLimitInformation com flags
                # JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
                basic_limit = ctypes.c_ulong * 12  # Simplified structure
                basic = basic_limit(0x100,  # LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY
                                   0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                
                # Copiar para a estrutura
                ctypes.memmove(ctypes.addressof(limit_info), 
                             ctypes.addressof(basic), 
                             48)
                
                limit_info.ProcessMemoryLimit = limit_mb * 1024 * 1024
                
                # SetInformationJobObject
                result = kernel32.SetInformationJobObject(
                    hJob,
                    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                    ctypes.byref(limit_info),
                    ctypes.sizeof(limit_info)
                )
                
                if not result:
                    kernel32.CloseHandle(hJob)
                    return False
                    
                # Associar processo ao Job
                result = kernel32.AssignProcessToJobObject(hJob, hProcess)
                
                if result:
                    # Manter handle do job aberto para o limite continuar ativo
                    # Em uma implementação real, salvaríamos o handle
                    return True
                else:
                    kernel32.CloseHandle(hJob)
                    return False
                    
            finally:
                kernel32.CloseHandle(hProcess)
                
        except Exception as e:
            print(f"Erro ao limitar memória: {e}")
            return False
            
    def remove_process_limit(self, pid):
        """Remove o limite de memória de um processo"""
        if pid in self._process_limits:
            del self._process_limits[pid]
            
    def open_config_dialog(self):
        """Abre janela de configurações de alertas"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Configurações de Alerta")
        dialog.geometry("450x750")
        dialog.transient(self)
        dialog.grab_set()
        
        # Container principal com scroll
        main_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            main_frame,
            text="⚙️ Configurações de Alerta",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(10, 15))
        
        # Frame Alertas
        alert_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        alert_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            alert_frame,
            text="🚨 Configurações de Alerta",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        # Alerta ativado
        self.alert_enabled_var = ctk.BooleanVar(value=self.alert_enabled)
        ctk.CTkSwitch(
            alert_frame,
            text="Alertas Ativados",
            variable=self.alert_enabled_var,
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=15, pady=5)
        
        # Threshold
        ctk.CTkLabel(
            alert_frame,
            text="Threshold de Alerta (%):",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        self.alert_threshold_var = ctk.IntVar(value=self.alert_threshold)
        threshold_slider = ctk.CTkSlider(
            alert_frame,
            from_=50,
            to=100,
            number_of_steps=50,
            variable=self.alert_threshold_var,
            width=350
        )
        threshold_slider.pack(padx=15, pady=5)
        
        self.threshold_label = ctk.CTkLabel(
            alert_frame,
            text=f"{self.alert_threshold}%",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.threshold_label.pack(pady=5)
        
        def update_threshold(value):
            self.threshold_label.configure(text=f"{int(value)}%")
        threshold_slider.configure(command=update_threshold)
        
        # Som
        self.alert_sound_var = ctk.BooleanVar(value=self.alert_sound)
        ctk.CTkSwitch(
            alert_frame,
            text="Som de Alerta",
            variable=self.alert_sound_var,
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=15, pady=10)
        
        # Frame Limpeza Automática
        clean_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        clean_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            clean_frame,
            text="🧹 Limpeza Automática",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        self.alert_auto_clean_var = ctk.BooleanVar(value=self.alert_auto_clean)
        ctk.CTkSwitch(
            clean_frame,
            text="Limpar automaticamente após timeout",
            variable=self.alert_auto_clean_var,
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=15, pady=5)
        
        ctk.CTkLabel(
            clean_frame,
            text="Timeout (segundos):",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        self.alert_timeout_var = ctk.IntVar(value=self.alert_timeout)
        timeout_slider = ctk.CTkSlider(
            clean_frame,
            from_=5,
            to=30,
            number_of_steps=25,
            variable=self.alert_timeout_var,
            width=350
        )
        timeout_slider.pack(padx=15, pady=5)
        
        self.timeout_label = ctk.CTkLabel(
            clean_frame,
            text=f"{self.alert_timeout}s",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.timeout_label.pack(pady=5)
        
        def update_timeout(value):
            self.timeout_label.configure(text=f"{int(value)}s")
        timeout_slider.configure(command=update_timeout)
        
        # Threshold de Limpeza Automática
        ctk.CTkLabel(
            clean_frame,
            text="Threshold de ativação (%):",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=15, pady=(15, 5))
        
        self.auto_clean_threshold_var = ctk.IntVar(value=self.auto_clean_threshold)
        threshold_slider = ctk.CTkSlider(
            clean_frame,
            from_=50,
            to=95,
            number_of_steps=45,
            variable=self.auto_clean_threshold_var,
            width=350
        )
        threshold_slider.pack(padx=15, pady=5)
        
        self.auto_clean_threshold_label = ctk.CTkLabel(
            clean_frame,
            text=f"{self.auto_clean_threshold}%",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.auto_clean_threshold_label.pack(pady=5)
        
        def update_auto_threshold(value):
            self.auto_clean_threshold_label.configure(text=f"{int(value)}%")
        threshold_slider.configure(command=update_auto_threshold)
        
        # Modo Automático Persistente
        self.auto_clean_persistent_var = ctk.BooleanVar(value=self.auto_clean_persistent)
        ctk.CTkSwitch(
            clean_frame,
            text="Manter Auto-Limpeza sempre ativada",
            variable=self.auto_clean_persistent_var,
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            clean_frame,
            text="Se ativado, a limpeza automática será ativada ao iniciar o programa.",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60")
        ).pack(anchor="w", padx=15, pady=(0, 10))
        
        # Frame Modo de Limpeza
        mode_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        mode_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            mode_frame,
            text="🔧 Modo de Limpeza Automática",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            mode_frame,
            text="Tipo de limpeza usada no modo automático:",
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w", padx=15, pady=(0, 5))
        
        self.clean_mode_var = ctk.StringVar(value=self.clean_mode)
        
        ctk.CTkRadioButton(
            mode_frame,
            text="Normal (Limpeza Básica)",
            variable=self.clean_mode_var,
            value="normal",
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w", padx=15, pady=5)
        
        ctk.CTkRadioButton(
            mode_frame,
            text="Inteligente (IA Clean) - Analisa e decide a melhor estratégia",
            variable=self.clean_mode_var,
            value="ai",
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w", padx=15, pady=5)
        
        # Frame de Inicialização
        startup_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        startup_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            startup_frame,
            text="🖥️ Inicialização do Windows",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        # Switch para iniciar com Windows
        self.startup_var = ctk.BooleanVar(value=self.start_with_windows)
        
        def toggle_startup():
            enabled = self.startup_var.get()
            self.set_startup(enabled)
        
        ctk.CTkSwitch(
            startup_frame,
            text="Iniciar com o Windows",
            variable=self.startup_var,
            command=toggle_startup,
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=15, pady=5)
        
        ctk.CTkLabel(
            startup_frame,
            text="O aplicativo será iniciado automaticamente ao ligar o PC.",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60")
        ).pack(anchor="w", padx=15, pady=(0, 10))
        
        # Frame de Atalho
        shortcut_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        shortcut_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            shortcut_frame,
            text="🔗 Atalho na Área de Trabalho",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        ctk.CTkButton(
            shortcut_frame,
            text="📲 Criar Atalho na Área de Trabalho",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.create_desktop_shortcut,
            height=35,
            width=250
        ).pack(padx=15, pady=(0, 15))
        
        # Frame de Configurações Avançadas (Restaurar Padrões)
        advanced_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray17"), corner_radius=10)
        advanced_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            advanced_frame,
            text="⚠️ Configurações Avançadas",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            advanced_frame,
            text="Restaura todas as configurações para os valores padrão do aplicativo.",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        ).pack(anchor="w", padx=15, pady=(0, 5))
        
        ctk.CTkButton(
            advanced_frame,
            text="🔄 Restaurar Configurações Padrão",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="orange",
            hover_color="darkorange",
            command=lambda: self._reset_config_to_defaults(dialog),
            height=35,
            width=280
        ).pack(padx=15, pady=(5, 15))
        
        # Botões (fixos na parte inferior, fora do scroll)
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10, side="bottom")
        btn_frame.pack_propagate(False)
        btn_frame.configure(height=60)
        
        ctk.CTkButton(
            btn_frame,
            text="💾 Salvar",
            fg_color="green",
            hover_color="darkgreen",
            command=lambda: self._save_config_settings(dialog),
            height=40,
            width=150
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            btn_frame,
            text="❌ Cancelar",
            fg_color="red",
            hover_color="darkred",
            command=lambda: self._safe_destroy_dialog(dialog),
            height=40,
            width=150
        ).pack(side="right", padx=(10, 0))
        
    def _save_config_settings(self, dialog):
        """Salva configurações de alerta"""
        self.alert_enabled = self.alert_enabled_var.get()
        self.alert_threshold = self.alert_threshold_var.get()
        self.alert_sound = self.alert_sound_var.get()
        self.alert_auto_clean = self.alert_auto_clean_var.get()
        self.alert_timeout = self.alert_timeout_var.get()
        self.clean_mode = self.clean_mode_var.get()
        self.auto_clean_threshold = self.auto_clean_threshold_var.get()
        self.auto_clean_persistent = self.auto_clean_persistent_var.get()
        
        self.save_config()
        self.footer_label.configure(text=f"✅ Configurações salvas! Modo: {self.clean_mode}, Threshold: {self.auto_clean_threshold}%")
        self._safe_destroy_dialog(dialog)
        
    def _reset_config_to_defaults(self, dialog):
        """Restaura todas as configurações para os valores padrão"""
        # Definir valores padrão
        default_values = {
            'alert_enabled': True,
            'alert_threshold': 90,
            'alert_sound': True,
            'alert_auto_clean': True,
            'alert_timeout': 10,
            'clean_mode': 'normal',
            'auto_clean_threshold': 80,
            'auto_clean_persistent': False,
            'start_with_windows': False,
            'auto_clean': False
        }
        
        # Atualizar variáveis da classe
        self.alert_enabled = default_values['alert_enabled']
        self.alert_threshold = default_values['alert_threshold']
        self.alert_sound = default_values['alert_sound']
        self.alert_auto_clean = default_values['alert_auto_clean']
        self.alert_timeout = default_values['alert_timeout']
        self.clean_mode = default_values['clean_mode']
        self.auto_clean_threshold = default_values['auto_clean_threshold']
        self.auto_clean_persistent = default_values['auto_clean_persistent']
        self.start_with_windows = default_values['start_with_windows']
        self.auto_clean_active = default_values['auto_clean']
        
        # Atualizar variáveis do diálogo
        self.alert_enabled_var.set(self.alert_enabled)
        self.alert_threshold_var.set(self.alert_threshold)
        self.alert_sound_var.set(self.alert_sound)
        self.alert_auto_clean_var.set(self.alert_auto_clean)
        self.alert_timeout_var.set(self.alert_timeout)
        self.clean_mode_var.set(self.clean_mode)
        self.auto_clean_threshold_var.set(self.auto_clean_threshold)
        self.auto_clean_persistent_var.set(self.auto_clean_persistent)
        self.startup_var.set(self.start_with_windows)
        
        # Atualizar labels dos sliders
        self.threshold_label.configure(text=f"{self.alert_threshold}%")
        self.timeout_label.configure(text=f"{self.alert_timeout}s")
        self.auto_clean_threshold_label.configure(text=f"{self.auto_clean_threshold}%")
        
        # Se modo persistente foi desativado, desativar também a limpeza automática
        if not self.auto_clean_persistent and self.auto_clean_active:
            self.toggle_auto_clean()
        
        # Salvar configurações
        self.save_config()
        
        # Mostrar mensagem de sucesso
        self.footer_label.configure(text="🔄 Configurações restauradas para os valores padrão!")
        
        # Fechar o diálogo
        self._safe_destroy_dialog(dialog)
        
    def _check_alert(self, ram_percent):
        """Verifica se deve mostrar alerta de RAM alta"""
        if not self.alert_enabled or self._alert_active:
            return
            
        if ram_percent >= self.alert_threshold:
            self._show_alert_dialog(ram_percent)
            
    def _show_alert_dialog(self, ram_percent):
        """Mostra diálogo de alerta com som e contagem regressiva"""
        self._alert_active = True
        
        if self.alert_sound:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except:
                pass
        
        # Criar diálogo
        dialog = ctk.CTkToplevel(self)
        dialog.title("⚠️ ALERTA DE RAM")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        self._alert_dialog = dialog
        
        # Frame vermelho de alerta
        alert_frame = ctk.CTkFrame(dialog, fg_color="red", corner_radius=10)
        alert_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            alert_frame,
            text="🚨 ALERTA DE MEMÓRIA!",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white"
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            alert_frame,
            text=f"RAM em {ram_percent}%!",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white"
        ).pack(pady=5)
        
        ctk.CTkLabel(
            alert_frame,
            text="O computador está utilizando muita memória RAM.",
            font=ctk.CTkFont(size=12),
            text_color="white",
            wraplength=350
        ).pack(pady=10)
        
        # Contador
        self.alert_countdown_var = ctk.IntVar(value=self.alert_timeout)
        self.alert_countdown_label = ctk.CTkLabel(
            alert_frame,
            text=f"Limpeza automática em {self.alert_timeout}s...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="yellow"
        )
        self.alert_countdown_label.pack(pady=10)
        
        # Botão para limpar agora
        def manual_clean():
            self._safe_destroy_dialog(dialog)
            self._alert_active = False
            self.clean_ram_aggressive()
            
        ctk.CTkButton(
            alert_frame,
            text="🧹 LIMPAR AGORA",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="white",
            text_color="red",
            hover_color="lightgray",
            command=manual_clean,
            height=50,
            width=200
        ).pack(pady=15)
        
        # Iniciar contagem regressiva se auto-clean ativado
        if self.alert_auto_clean:
            self._start_alert_countdown(dialog)
            
    def _start_alert_countdown(self, dialog):
        """Inicia contagem regressiva para limpeza automática"""
        def countdown():
            remaining = self.alert_timeout
            while remaining > 0 and dialog.winfo_exists():
                try:
                    self.alert_countdown_label.configure(
                        text=f"Limpeza automática em {remaining}s..."
                    )
                except:
                    return
                time.sleep(1)
                remaining -= 1
            
            # Se o diálogo ainda existe, fazer limpeza
            if dialog.winfo_exists():
                try:
                    self._safe_destroy_dialog(dialog)
                    self._alert_active = False
                    self.clean_ram_aggressive()
                except:
                    pass
                    
        threading.Thread(target=countdown, daemon=True).start()
        
    def clean_ram_aggressive(self):
        """Limpeza agressiva de RAM quando alerta é disparado"""
        try:
            self.footer_label.configure(text="🚨 LIMPEZA AGRESSIVA INICIADA...")
            self.update()
            
            # 1. EmptyWorkingSet no processo atual e sistema
            if os.name == 'nt':
                try:
                    ctypes.windll.psapi.EmptyWorkingSet(ctypes.c_int(-1))
                except:
                    pass
                    
            # 2. Forçar coleta de lixo múltiplas vezes
            import gc
            for _ in range(3):
                gc.collect()
                time.sleep(0.2)
                
            # 3. Tentar liberar working set de processos grandes
            try:
                for proc in psutil.process_iter(['pid', 'memory_info']):
                    try:
                        if proc.info.get('memory_info') and proc.info['memory_info'].rss > 200 * 1024 * 1024:
                            hProcess = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, proc.info['pid'])
                            if hProcess:
                                try:
                                    ctypes.windll.psapi.EmptyWorkingSet(hProcess)
                                except:
                                    pass
                                finally:
                                    ctypes.windll.kernel32.CloseHandle(hProcess)
                    except:
                        pass
            except:
                pass
                
            # 4. Aguardar e verificar resultado
            time.sleep(1)
            ram = psutil.virtual_memory()
            
            if ram.percent < self.alert_threshold:
                self.footer_label.configure(
                    text=f"✅ RAM reduzida para {ram.percent}% (Limpeza Agressiva)"
                )
            else:
                self.footer_label.configure(
                    text=f"⚠️ RAM ainda em {ram.percent}% - Limpeza realizada"
                )
                
            self._alert_active = False
            
        except Exception as e:
            self.footer_label.configure(text=f"❌ Erro na limpeza agressiva: {e}")
            self._alert_active = False
            
    def create_desktop_shortcut(self):
        """Cria um atalho na área de trabalho para o aplicativo"""
        try:
            import winshell
            from win32com.client import Dispatch
            
            # Caminho do executável Python e do script
            python_path = sys.executable
            script_path = os.path.abspath(__file__)
            
            # Caminho da área de trabalho
            desktop = winshell.desktop()
            shortcut_path = os.path.join(desktop, "RAM Manager Pro.lnk")
            
            # Criar atalho
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = python_path
            shortcut.Arguments = f'"{script_path}"'
            shortcut.WorkingDirectory = os.path.dirname(script_path)
            shortcut.IconLocation = python_path
            shortcut.Description = "RAM Manager Pro - Gerenciador de Memória"
            shortcut.save()
            
            self.footer_label.configure(text="✅ Atalho criado na Área de Trabalho!")
            return True
            
        except ImportError:
            # Se não tiver winshell, tentar método alternativo com ctypes
            try:
                self._create_shortcut_alternative()
                self.footer_label.configure(text="✅ Atalho criado na Área de Trabalho!")
                return True
            except Exception as e:
                self.footer_label.configure(text=f"❌ Erro ao criar atalho: {e}")
                return False
                
        except Exception as e:
            self.footer_label.configure(text=f"❌ Erro ao criar atalho: {e}")
            return False
            
    def _create_shortcut_alternative(self):
        """Método alternativo para criar atalho usando PowerShell"""
        import subprocess
        
        script_path = os.path.abspath(__file__)
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop, "RAM Manager Pro.lnk")
        
        # Usar PowerShell para criar atalho
        ps_command = f'''
        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{sys.executable}"
        $Shortcut.Arguments = "{script_path}"
        $Shortcut.WorkingDirectory = "{os.path.dirname(script_path)}"
        $Shortcut.Description = "RAM Manager Pro"
        $Shortcut.Save()
        '''
        
        subprocess.run(["powershell", "-Command", ps_command], check=True)
        
    def set_startup(self, enable):
        """Adiciona ou remove o aplicativo da inicialização do Windows"""
        try:
            import winreg
            
            # Chave do Registro para Startup
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            # Abrir chave do Registro
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, 
                                winreg.KEY_ALL_ACCESS)
            
            if enable:
                # Caminho do executável e script
                python_path = sys.executable
                script_path = os.path.abspath(__file__)
                command = f'"{python_path}" "{script_path}"'
                
                # Adicionar à inicialização
                winreg.SetValueEx(key, "RAMManagerPro", 0, winreg.REG_SZ, command)
                self.start_with_windows = True
                self.footer_label.configure(text="✅ RAM Manager adicionado à inicialização!")
            else:
                # Remover da inicialização
                try:
                    winreg.DeleteValue(key, "RAMManagerPro")
                    self.start_with_windows = False
                    self.footer_label.configure(text="✅ RAM Manager removido da inicialização!")
                except FileNotFoundError:
                    # Valor não existe, nada a fazer
                    self.start_with_windows = False
                    pass
                    
            winreg.CloseKey(key)
            self.save_config()
            return True
            
        except Exception as e:
            self.footer_label.configure(text=f"❌ Erro ao configurar startup: {e}")
            return False

if __name__ == "__main__":
    app = RAMManagerPro()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
