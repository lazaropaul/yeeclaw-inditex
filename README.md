# yeeclaw-inditex

## HackUPC 2026 project for Inditex Tech

Implementación de un sistema de gestión de silos automatizados que optimiza el flujo de entrada (Input) y salida (Output) mediante optimización matemática y lógica de priorización dinámica.

### Características Clave

- **Optimización MILP (Input):** Algoritmo de asignación de almacenamiento que minimiza el tiempo de ciclo y penaliza violaciones de la regla Z (profundidad).
- **Prioridad Dinámica (Output):** Algoritmo de secuenciación de salida que reordena la recuperación de cajas basándose en la posición actual de los shuttles y la regla Z, minimizando el *makespan*.
- **Restricción de Recursos:** Gestión estricta de **1 Shuttle compartido por nivel de altura (Y)**, coordinando operaciones de entrada y salida sin colisiones.
- **Formación de Pallets:** Consolidación automática de cajas por destino (12 cajas/pallet) con capacidad para 8 pallets simultáneos.

### Métricas de Éxito (KPIs)
- **Pallets Completos:** 100% de eficiencia en pallets formados.
- **Throughput:** ~12 pallets/hora (escala linealmente con el volumen).
- **Regla Z:** Cumplimiento total de restricciones de profundidad y reubicación.

### Instalación y Ejecución

1. Instalar dependencias:
   ```bash
   pip install pulp
   ```
2. Ejecutar simulación:
   ```bash
   python main.py
   ```

### Arquitectura
- `src/model/silo_state.py`: Modelo físico del silo (Grid 4x2x60x8x2).
- `src/algorithms/milp_optimizer.py`: Solver matemático para asignación de entrada.
- `src/algorithms/pallet_optimizer.py`: Lógica de despacho y priorización de salida.
