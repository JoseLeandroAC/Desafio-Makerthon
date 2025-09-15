from deepface import DeepFace
import cv2
import os
import time

# Define a pasta que contém as imagens das pessoas conhecidas
banco_de_dados = "imagens_conhecidas"

print("\n--- MENU ---")
print("[1] Executar Reconhecimento Facial")
print("[2] Adicionar Novas Fotos")
print("------------")

modo = input("Escolha um modo (1 ou 2): ")

if modo == '1':
    # --- MODO DE RECONHECIMENTO FACIAL ---
    
    webcam = cv2.VideoCapture(0)
    print("\nWebcam iniciada. Pressione 'q' para sair.")
    
    frame_count = 0
    skip_frames = 10 
    last_face_info = None
    last_text_info = 'Nenhum rosto detectado'
    cor = (0, 0, 255) # Cor inicial do quadrado
    
    while True:
        ret, frame = webcam.read()
        if not ret:
            break
            
        frame_count += 1
        
        if frame_count % skip_frames == 0:
            try:
                rostos_detectados = DeepFace.extract_faces(
                    img_path=frame, 
                    detector_backend="retinaface",
                    enforce_detection=False
                )
                
                if rostos_detectados:
                    print("\n> Rosto detectado com sucesso. Tentando fazer o reconhecimento...")
                    last_face_info = rostos_detectados[0]['facial_area']
                    
                    x = last_face_info['x']
                    y = last_face_info['y']
                    w = last_face_info['w']
                    h = last_face_info['h']
                    
                    rosto_recortado = frame[y:y+h, x:x+w]
    
                    try:
                        resultados = DeepFace.find(
                            img_path=rosto_recortado, 
                            db_path=banco_de_dados, 
                            model_name="Facenet", 
                            distance_metric="euclidean_l2",
                            enforce_detection=False,
                            detector_backend="retinaface"
                        )
                        
                        if resultados and not resultados[0].empty:
                            distancia = resultados[0]['distance'][0]
                            
                            limite_distancia_confianca = 0.65
    
                            if distancia < limite_distancia_confianca:
                                caminho_identidade = resultados[0]['identity'][0]
                                nome_pessoa = caminho_identidade.split(os.path.sep)[-2]
                                last_text_info = f"{nome_pessoa} (dist: {distancia:.2f})"
                                cor = (0, 255, 0)
                            else:
                                last_text_info = f"Desconhecido (dist: {distancia:.2f})"
                                cor = (0, 0, 255)
                        else:
                            last_text_info = 'Desconhecido'
                            cor = (0, 0, 255)
                    except Exception as e:
                        last_text_info = 'Desconhecido'
                        print(f"!!! ERRO NA COMPARAÇÃO: {e}")
                else:
                    last_face_info = None
                    last_text_info = 'Nenhum rosto detectado'
                    cor = (0, 0, 255)
            except Exception as e:
                last_face_info = None
                last_text_info = 'Nenhum rosto detectado'
                cor = (0, 0, 255)
                print(f"!!! ERRO NA DETECÇÃO: {e}")
        
        if last_face_info:
            x = last_face_info['x']
            y = last_face_info['y']
            w = last_face_info['w']
            h = last_face_info['h']
            
            cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 2)
            cv2.putText(frame, last_text_info, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, cor, 2)
        else:
            cv2.putText(frame, last_text_info, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, cor, 2)
    
        cv2.imshow('Reconhecimento Facial', frame)
    
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    webcam.release()
    cv2.destroyAllWindows()

elif modo == '2':
    # --- MODO DE ADICIONAR FOTOS ---
    
    nome_da_pessoa = input("\nDigite o nome da pessoa: ")
    nome_da_pessoa = nome_da_pessoa.replace(" ", "_") # Remove espaços para evitar erros
    
    caminho_pasta = os.path.join(banco_de_dados, nome_da_pessoa)
    os.makedirs(caminho_pasta, exist_ok=True)
    
    webcam = cv2.VideoCapture(0)
    print("Câmera aberta. Pressione 's' para salvar a foto ou 'q' para sair.")
    
    while True:
        ret, frame = webcam.read()
        if not ret:
            break
        
        cv2.imshow("Adicionar Fotos", frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('s'):
            timestamp = int(time.time())
            caminho_foto = os.path.join(caminho_pasta, f"{nome_da_pessoa}_{timestamp}.jpg")
            cv2.imwrite(caminho_foto, frame)
            print(f"Foto salva em: {caminho_foto}")
            print("Pressione 's' novamente para tirar outra foto ou 'q' para sair.")
            
        elif key == ord('q'):
            break
    
    webcam.release()
    cv2.destroyAllWindows()
    
    # --- NOVO CÓDIGO PARA AUTOMATIZAR A REMOÇÃO DOS ARQUIVOS DE CACHE ---
    print("\nAutomatizando a limpeza do cache...")
    try:
        for arquivo in os.listdir(banco_de_dados):
            if arquivo.endswith(".pkl"):
                caminho_arquivo = os.path.join(banco_de_dados, arquivo)
                os.remove(caminho_arquivo)
                print(f"Arquivo de cache removido: {arquivo}")
        print("Cache de reconhecimento facial limpo com sucesso!")
    except Exception as e:
        print(f"Erro ao limpar o cache: {e}")
    # --- FIM DO NOVO CÓDIGO ---
    
else:
    print("\nOpção inválida. Por favor, escolha 1 ou 2.")
