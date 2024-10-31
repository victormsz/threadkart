import pygame
import threading as thr
import random as rnd
import time
import queue
import os
import math

WIDTH, HEIGHT = 1280, 640
CAR_WIDTH, CAR_HEIGHT = 144, 144
CAR_Y_BASE = 290  # Altura base pros carros
VERTICAL_SPACING = 35  # Distância entre os carros
PitStop = []
waitTimes = []

class corredor(thr.Thread):
    def __init__(self, nome, velocidade, poder, competidores, update_queue, index, manager):
        thr.Thread.__init__(self)
        self.nome = nome
        self.velocidade = velocidade
        self.poder = poder
        self.vitorias = 0
        self.trajeto = 0
        self.competidores = competidores
        self.acelerando = 5
        self.update_queue = update_queue
        self.index = index 
        self.estado = 0 
        self.manager = manager

    def azar(self):
        perdeu = rnd.randrange(8, 12) - self.poder
        self.trajeto -= perdeu
        if self.trajeto < 0:
            self.trajeto = 0
        print(f'{self.nome} perdeu {perdeu}m')

    def jogar_bomba(self):
        alvo = rnd.choice(self.competidores)
        if alvo.estado != 4:
            ataque = self.poder + rnd.randrange(1, 5)
            alvo.trajeto -= ataque
            alvo.acelerando = 0
            alvo.estado = 2
            if alvo.trajeto < 0:
                alvo.trajeto = 0
            print(f'{self.nome} jogou uma bomba em {alvo.nome} (ele perdeu {ataque}m)!')
            # Termina a rotação do alvo em 1 segundo, estado 0 é o de andar normal
            if rnd.randrange(0, 4) < 2:
                print(f'O carro de {alvo.nome} quebrou!')
                alvo.estado = 3
                thr.Timer(0.5, lambda: setattr(alvo, 'estado', 4 )).start()
                thr.Timer(0.5, lambda: self.manager.add_car_to_pit_stop((alvo, float(rnd.uniform(1,3)), time.time()))).start()
            else:
                thr.Timer(0.5, lambda: setattr(alvo, 'estado', 1 )).start()
                thr.Timer(1.5, lambda: setattr(alvo, 'estado', 0 )).start()

    def boost(self):
        turbo = 5 + (self.velocidade + self.poder)/2
        self.trajeto += turbo
        self.acelerando = 5
        print(f'{self.nome} usou um boost e ganhou {turbo}m!')

    def run(self):
        global vencedor
        self.trajeto = 0
        while vencedor is None:
            if self.acelerando < 5:
                self.acelerando += 1
            else:
                if self.estado != 4:
                    self.trajeto += self.velocidade + rnd.randrange(-2, 2)
                self.update_queue.put((self.nome, self.trajeto, self.index, self.estado))  # Atualiza posição e estado na fila
                time.sleep(0.5)
                print(f'{self.trajeto}m - {self.nome}')
                if self.trajeto >= 500:
                    vencedor = self.nome
                    self.update_queue.put(('Vencedor', self.nome))  # Notifica o vencedor
                    print(f'Vencedor(a): {vencedor}')
                    break

def load_background(image_name):
    background = pygame.image.load(os.path.join('sprites', image_name))
    return pygame.transform.scale(background, (WIDTH, HEIGHT))

# Função para desenhar a corrida na tela
def draw_race(screen, carros_animados, carros_rot_animados, carros_tartaruga_animados, carros_lakitu_animados, car_positions, current_frames, car_offsets, car_states):
    # Desenha os carros na posição atual com base no frame atual
    for i, (car_frames, car_rot_frames, car_tartaruga_frames, car_lakitu_frames, pos, offset, estado) in enumerate(zip(carros_animados, carros_rot_animados, carros_tartaruga_animados, carros_lakitu_animados, car_positions, car_offsets, car_states)):
        if estado == 4:
            continue
        elif estado == 3:
            current_frame = current_frames[i] % len(car_lakitu_frames)
            screen.blit(car_lakitu_frames[current_frame], (pos, CAR_Y_BASE + i * VERTICAL_SPACING + offset - 90))
        elif estado == 2:
            current_frame = current_frames[i] % len(car_tartaruga_frames)
            screen.blit(car_tartaruga_frames[current_frame], (pos, CAR_Y_BASE + i * VERTICAL_SPACING + offset))
        elif estado == 1:
            # Usa a animação de rotação
            current_frame = current_frames[i] % len(car_rot_frames)  # Roda o frame atual e volta do 0 quando chega no max
            screen.blit(car_rot_frames[current_frame], (pos, CAR_Y_BASE + i * VERTICAL_SPACING + offset)) # Desenha o carro na posicao calculada através do seno, da linha base e do espaçamento
        elif estado == 0:
            # Usa a animação normal
            current_frame = current_frames[i] % len(car_frames)  # Roda o frame atual e volta do 0 quando chega no max
            screen.blit(car_frames[current_frame], (pos, CAR_Y_BASE + i * VERTICAL_SPACING + offset)) #Mesmo só que com a animação normal
    pygame.display.flip()

# Função para carregar os frames de animação de cada carro
def load_car_frames(car_file_template, num_frames):
    frames = []
    sprite_folder = os.path.join('sprites', car_file_template)
    for i in range(1, num_frames + 1):
        frame = pygame.transform.scale(
            pygame.image.load(sprite_folder.format(i)), (CAR_WIDTH, CAR_HEIGHT)
        )
        frames.append(frame)
    return frames

def load_lakitu_frames(car_file_template, num_frames):
    frames = []
    sprite_folder = os.path.join('sprites', car_file_template)
    for i in range(1, num_frames + 1):
        frame = pygame.transform.scale(
            pygame.image.load(sprite_folder.format(i)), (192, 288)
        )
        frames.append(frame)
    return frames

def load_title(image_name):
    title = pygame.image.load(os.path.join('sprites', image_name))
    return pygame.transform.scale(title, (792, 228))  # Ajuste a altura do título conforme necessário


class PitStopManager(thr.Thread):
    def __init__(self, pit_stop, strategy="FCFS"):
        super().__init__()
        self.PitStop = pit_stop  # Lista de carros no pit stop
        self.waitTimes = []  # Lista para armazenar os tempos de espera dos carros
        self.strategy = strategy  # Estrategia de pit stop: "FCFS" ou "SJF"
        self.running = True  # Controle para parar a thread
        self.condition = thr.Condition()  # Para sincronização

    def run(self):
        #Executa a estratégia escolhida em uma thread separada.
        while self.running:
            with self.condition:
                # Aguarda até que um carro seja adicionado ou que a execução seja interrompida
                self.condition.wait_for(lambda: len(self.PitStop) > 0 or not self.running)
            if not self.running:
                break
            # Escolhe a estratégia e executa o pit stop para um carro
            if self.strategy == "FCFS":
                self.pitStopFCFS()
            elif self.strategy == "SJF":
                self.pitStopSJF()

    def pitStopFCFS(self):
        #First-Come-First-Serve (FCFS) Strategy.
        timestart = time.time()
        if len(self.PitStop) > 0:
            car = self.PitStop[0]
            i = 0
            while time.time() <= (timestart + car[1]) and self.running:
                if i == 0:
                    self.waitTimes.append(time.time() - car[2])
                i = 1
                time.sleep(0.01)  # Evita bloqueio
            car[0].estado = 0
            print(f"Carro de {car[0].nome} consertado! Restam {len(self.PitStop)} no pit stop.")
            self.PitStop.pop(0)

    def pitStopSJF(self):
        #Shortest Job First (SJF) Strategy.
        timestart = time.time()
        if len(self.PitStop) > 0:
            self.PitStop.sort(key=lambda x: x[1])
            car = self.PitStop[0]
            i = 0
            while time.time() <= (timestart + car[1]) and self.running:
                if i == 0:
                    self.waitTimes.append(time.time() - car[2])
                i = 1
                time.sleep(0.01)  # Evita bloqueio
            car[0].estado = 0
            print(f"Carro de {car[0].nome} consertado! Restam {len(self.PitStop)} no pit stop.")
            self.PitStop.pop(0)

    def add_car_to_pit_stop(self, car_data):
        #Adiciona um carro ao pit stop e notifica a thread.
        with self.condition:
            self.PitStop.append(car_data)
            self.condition.notify()  # Notifica que há um novo carro no pit stop

    def stop(self):
        #Para o loop do pit stop e exibe métricas ao final.
        self.running = False
        with self.condition:
            self.condition.notify()  # Notifica para encerrar o `wait`
        if self.waitTimes:  # Verifica se há tempos de espera registrados
            self.waitTimes.sort()
            print("Minimum wait time:", self.waitTimes[0])
            self.waitTimes.sort(reverse=True)
            print("Maximum wait time:", self.waitTimes[0])
            avgTime = sum(self.waitTimes) / len(self.waitTimes)
            print("Average wait time:", avgTime)

class PowerUpManager(thr.Thread):
    def __init__(self, cars, strategy="SB", max_count=3):
        super().__init__()
        self.cars = cars  # Lista de carros que podem receber power-ups
        self.strategy = strategy  # Escolha da estratégia de sincronização
        self.running = True  # Controla a execução da thread
        self.max_count = max_count  # Número máximo de carros para semáforo de contagem

        # Configura o mecanismo de sincronização
        if self.strategy == "SB":
            self.semaforo = thr.Semaphore(1)  # Semáforo binário (exclusão mútua)
        elif self.strategy == "MO":
            self.lock = thr.Lock()  # Monitor
        elif self.strategy == "SC":
            self.semaforo = thr.Semaphore(max_count)  # Semáforo de contagem

    def run(self):
        #Executa o sorteio de power-ups enquanto a thread estiver ativa.
        while self.running:
            if self.strategy == "SC":
                self.sorteio_power_up_contagem()  # Sorteio para múltiplos carros
            else:
                car = rnd.choice(self.cars)  # Escolhe um carro aleatoriamente
                self.sorteio_power_up(car)  # Chama o sorteio com a sincronização apropriada
            time.sleep(1)  # Intervalo entre sorteios (ajuste conforme necessário)

    def sorteio_power_up_contagem(self):
        #Sorteia power-ups para múltiplos carros no caso do semáforo de contagem.
        selected_cars = rnd.sample(self.cars, min(self.max_count, len(self.cars)))  # Seleciona até max_count carros
        for car in selected_cars:
            self.semaforo.acquire()  # Cada carro tenta adquirir o semáforo individualmente
            try:
                self.atribuir_power_up(car)
            finally:
                self.semaforo.release()  # Libera o semáforo para o próximo carro

    def sorteio_power_up(self, car):
        #Realiza o sorteio de power-ups para um carro."""
        if self.strategy == "SB":
            with self.semaforo:
                self.atribuir_power_up(car)
        else:
            with self.lock:
                self.atribuir_power_up(car)

    def atribuir_power_up(self, car):
        #Atribui um power-up ao carro na seção crítica.
        power_up = rnd.randrange(1, 3)
        if power_up == 1:
            car.azar()
            print(f"Carro de {car.nome} furou o pneu!")
        elif power_up == 2:
            car.jogar_bomba()
            print(f"Carro de {car.nome} recebeu um casco!")
        else:
            car.boost()
            print(f"Carro de {car.nome} recebeu um boost!")

    def stop(self):
        """Para a execução do gerenciador de power-ups."""
        self.running = False

# Função principal
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("SUPER THREADKART")

    background_speed = 8
    title_image = load_title('title.png')
    clock = pygame.time.Clock()
    running = True

    # Carrega o fundo e define as posições iniciais
    background_image = load_background('background.png')
    background_x1 = 0
    background_x2 = WIDTH

    # Carrega os frames de animação dos carros e rotação
    car1_frames = load_car_frames('mario{}.png', 2)  # Carro 1 tem 2 frames de animação
    car2_frames = load_car_frames('luigi{}.png', 2)  # Carro 2 tem 2 frames de animação
    car3_frames = load_car_frames('peach{}.png', 2)  # Carro 3 tem 2 frames de animação
    car4_frames = load_car_frames('bowser{}.png', 2)  # Carro 1 tem 2 frames de animação
    car5_frames = load_car_frames('toad{}.png', 2)  # Carro 2 tem 2 frames de animação
    car6_frames = load_car_frames('sonic{}.png', 2)  # Carro 3 tem 2 frames de animação
    car7_frames = load_car_frames('koopa{}.png', 2)  # Carro 3 tem 2 frames de animação

    car1_rot_frames = load_car_frames('mario_rot{}.png', 4)  # Animação de rotação
    car2_rot_frames = load_car_frames('luigi_rot{}.png', 4)  # Animação de rotação
    car3_rot_frames = load_car_frames('peach_rot{}.png', 4)  # Animação de rotação
    car4_rot_frames = load_car_frames('bowser_rot{}.png', 4)  # Animação de rotação
    car5_rot_frames = load_car_frames('toad_rot{}.png', 4)  # Animação de rotação
    car6_rot_frames = load_car_frames('sonic_rot{}.png', 4)  # Animação de rotação
    car7_rot_frames = load_car_frames('koopa_rot{}.png', 4)  # Animação de rotação

    car1_tartaruga_frames = load_car_frames('mario_tartaruga{}.png', 6)  # Animação de rotação
    car2_tartaruga_frames = load_car_frames('luigi_tartaruga{}.png', 6)  # Animação de rotação
    car3_tartaruga_frames = load_car_frames('peach_tartaruga{}.png', 6)  # Animação de rotação
    car4_tartaruga_frames = load_car_frames('bowser_tartaruga{}.png', 6)  # Animação de rotação
    car5_tartaruga_frames = load_car_frames('toad_tartaruga{}.png', 6)  # Animação de rotação
    car6_tartaruga_frames = load_car_frames('sonic_tartaruga{}.png', 6)  # Animação de rotação
    car7_tartaruga_frames = load_car_frames('koopa_tartaruga{}.png', 6)  # Animação de rotação

    car1_lakitu_frames = load_lakitu_frames('mario_lakitu{}.png', 6)  # Animação de rotação
    car2_lakitu_frames = load_lakitu_frames('luigi_lakitu{}.png', 6)  # Animação de rotação
    car3_lakitu_frames = load_lakitu_frames('peach_lakitu{}.png', 6)  # Animação de rotação
    car4_lakitu_frames = load_lakitu_frames('bowser_lakitu{}.png', 6)  # Animação de rotação
    car5_lakitu_frames = load_lakitu_frames('toad_lakitu{}.png', 6)  # Animação de rotação
    car6_lakitu_frames = load_lakitu_frames('sonic_lakitu{}.png', 6)  # Animação de rotação
    car7_lakitu_frames = load_lakitu_frames('koopa_lakitu{}.png', 6)  # Animação de rotação
    
    carros_animados = [car1_frames, car2_frames, car3_frames, car4_frames, car5_frames, car6_frames, car7_frames]
    carros_rot_animados = [car1_rot_frames, car2_rot_frames, car3_rot_frames, car4_rot_frames, car5_rot_frames, car6_rot_frames, car7_rot_frames]
    carros_tartaruga_animados = [car1_tartaruga_frames, car2_tartaruga_frames, car3_tartaruga_frames, car4_tartaruga_frames, car5_tartaruga_frames, car6_tartaruga_frames, car7_tartaruga_frames]  
    carros_lakitu_animados = [car1_lakitu_frames, car2_lakitu_frames, car3_lakitu_frames, car4_lakitu_frames, car5_lakitu_frames, car6_lakitu_frames, car7_lakitu_frames]    
    
    # Inicializa a fila de atualizações
    update_queue = queue.Queue()
    car_positions = [0, 0, 0, 0, 0, 0, 0]  # Posições iniciais dos carros
    current_frames = [0, 0, 0, 0, 0, 0, 0]  # Frame atual de cada carro
    car_offsets = [0, 0, 0, 0, 0, 0, 0]  # Variação vertical dos carros
    car_states = [False, False, False, False, False, False, False]  # Estado de rotação dos carros

    # Inicializa os corredores e suas threads
    global vencedor
    vencedor = None

    ############################################################################################################################
    #ESCOLHE A ESTRATEGIA DE ESCALONAMENTO
    pit_stop_manager = PitStopManager(PitStop, strategy="FCFS")
    pit_stop_manager.start()

    c1 = corredor('MARIO', 5, 7, [], update_queue, 0, pit_stop_manager)
    c2 = corredor('LUIGI', 6, 6, [], update_queue, 1, pit_stop_manager)
    c3 = corredor('PEACH', 7, 5, [], update_queue, 2, pit_stop_manager)
    c4 = corredor('BOWSER', 4, 8, [], update_queue, 3, pit_stop_manager)
    c5 = corredor('TOAD', 5, 5, [], update_queue, 4, pit_stop_manager)
    c6 = corredor('SONIC', 7, 3, [], update_queue, 5, pit_stop_manager)
    c7 = corredor('TROPA', 5, 4, [], update_queue, 6, pit_stop_manager)

    c1.competidores = [c2, c3, c4, c5, c6, c7]
    c2.competidores = [c1, c3, c4, c5, c6, c7]
    c3.competidores = [c1, c2, c4, c5, c6, c7]
    c4.competidores = [c2, c3, c1, c5, c6, c7]
    c5.competidores = [c2, c3, c4, c1, c6, c7]
    c6.competidores = [c2, c3, c4, c5, c1, c7]
    c7.competidores = [c2, c3, c4, c5, c1, c6]

    c1.start()
    c2.start()
    c3.start()
    c4.start()
    c5.start()
    c6.start()
    c7.start()

    cars = [c1, c2, c3, c4, c5, c6, c7]  # Lista de carros que podem receber power-ups

    ############################################################################################################################
    #ESCOLHE A ESTRATEGIA DE SINCRONISMO SB, MO E SC (Escolher o max_count nesse caso) 

    #Basicamente vai avaliar a distribuição de power ups no jogo
    power_up_manager = PowerUpManager(cars, strategy="SC", max_count = 4)
    power_up_manager.start()

    # Loop principal
    frame_counter = 0  # Contador de frames para alternar as animações
    while running:
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Atualiza as posições dos carros com base na fila de threads,
        while not update_queue.empty():
            data = update_queue.get() # Enquanto tiver informações no update_queue, ele vai levar para o data
            if data[0] == 'Vencedor':
                vencedor = data[1]
                running = False
            else: #se não tiver vencedor, vai continuar rodando
                name, trajeto, index, estado = data
                if name == 'MARIO':
                    car_positions[0] = trajeto * 2  # x2 para facilitar a visão do que está acontecendo na tela
                    car_states[0] = estado
                elif name == 'LUIGI':
                    car_positions[1] = trajeto * 2
                    car_states[1] = estado
                elif name == 'PEACH':
                    car_positions[2] = trajeto * 2
                    car_states[2] = estado
                elif name == 'BOWSER':
                    car_positions[3] = trajeto * 2  # x2 para facilitar a visão do que está acontecendo na tela
                    car_states[3] = estado
                elif name == 'TOAD':
                    car_positions[4] = trajeto * 2
                    car_states[4] = estado
                elif name == 'SONIC':
                    car_positions[5] = trajeto * 2
                    car_states[5] = estado
                elif name == 'TROPA':
                    car_positions[6] = trajeto * 2
                    car_states[6] = estado

        # Frames do jogo
        frame_counter += 1

        # Ele vai atualizar o frame do carro a cada 5 frames do jogo
        if frame_counter % 5 == 0:
            for i in range(len(current_frames)):
                # Escolhe a animação se ele estiver normal ou rodando
                animacao_atual = carros_tartaruga_animados[i] if car_states[i] == 3 else carros_tartaruga_animados[i] if car_states[i] == 2 else carros_rot_animados[i] if car_states[i] == 1 else carros_animados[i]
                
                # Avança um quadro toda vez que roda o % len faz ele reiniciar o frame depois do último quadro
                current_frames[i] = (current_frames[i] + 1) % len(animacao_atual)

        # Atualiza a posição do background (tanto da esquerda, quanto da direita)
        background_x1 -= background_speed
        background_x2 -= background_speed

        # Se o fundo sair completamente da tela, reposiciona-o à direita
        if background_x1 <= -WIDTH:
            background_x1 = WIDTH
        if background_x2 <= -WIDTH:
            background_x2 = WIDTH

        # Desenha o fundo na tela
        screen.blit(background_image, (background_x1, 0))
        screen.blit(background_image, (background_x2, 0))
        screen.blit(title_image, (236, 60))  # Desenha o título na parte superior

        # Posição verticual dos carros através de uma função seno
        amplitude = 10
        frequency = 0.1
        for i in range(len(car_offsets)):
            car_offsets[i] = amplitude * math.sin(frame_counter * frequency + i * 10) 

        # Desenha a corrida na tela
        draw_race(screen, carros_animados, carros_rot_animados, carros_tartaruga_animados, carros_lakitu_animados, car_positions, current_frames, car_offsets, car_states)
        clock.tick(30)  # Limita a 30 FPS

    pit_stop_manager.stop()
    pit_stop_manager.join()  # Espera a thread terminar antes de sair
    power_up_manager.stop()
    power_up_manager.join()
    pygame.quit()

if __name__ == "__main__":
    fim = 500  # Definindo a distância final
    main()