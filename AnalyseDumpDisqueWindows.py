#!/usr/bin/python3
# -*- coding: utf-8 -*-

import pytsk3
import regipy
import pyscca
import re
import LnkParse3
import pyevtx
import pyevt
import xml.etree.ElementTree
import locale
import pypff
import filetype
import shutil
import datetime
import sys
import argparse
import pathlib
import os

locale.setlocale(locale.LC_ALL, '')


def dump_fichier (pointeur_fichier,emplacement_fichier,dossier_dump,limite_mo_dump_fichier,is_file_mandatory_for_analysis) :

  if emplacement_fichier.find("/") == -1 :
       nom_fichier = emplacement_fichier
  else :
       nom_fichier = emplacement_fichier[(emplacement_fichier.rindex("/") +1):]

  dump_fichier = dossier_dump / nom_fichier

  taille_disponible_dossier_dump =  shutil.disk_usage(dossier_dump)[1]
  if  pointeur_fichier.info.meta.size > taille_disponible_dossier_dump :
      print ("Le fichier %s ne peut pas être dumpé, car il est plus lourd que l'emplacement disponible pour le dossier de dump" %emplacement_fichier )
      return(False)


  #Conversion octets / mo
  taille_fichier_mo = pointeur_fichier.info.meta.size / 1048576

  if taille_fichier_mo > limite_mo_dump_fichier and is_file_mandatory_for_analysis == False :
      print ("Le fichier %s ne sera pas dumpé, car il est d'une taille supérieure à la limite fixée lors du lancement du script : %fmo > %dmo" % (emplacement_fichier,taille_fichier_mo,limite_mo_dump_fichier))
      return(False)
  else :
      try:
            dump_fichier = open(dump_fichier,"wb")
            dump_fichier.write(pointeur_fichier.read_random(0, pointeur_fichier.info.meta.size))
            dump_fichier.close()
            return(True)
      except:
            return(False)


def analyse_sous_dossier_outlook (pointeur_sous_dossier_outlook,liste_sous_dossier_deja_lues,emplacement_dossier_parent,dossier_dump) :


    while pointeur_sous_dossier_outlook.get_number_of_sub_folders() != 0: 
        for sous_dossier_outlook in pointeur_sous_dossier_outlook.sub_folders :
            #Condition de sortie évitant les boucles infinies, puisque cela arrête l'analyse pour les sous-dossiers déjà analysés
            if emplacement_dossier_parent  + "/" +  sous_dossier_outlook.get_name() in liste_sous_dossier_deja_lues :
                return ()
            liste_sous_dossier_deja_lues.append(emplacement_dossier_parent + "/"  + sous_dossier_outlook.get_name() )
            if sous_dossier_outlook.get_number_of_sub_messages() != 0 :

                for message_courant in sous_dossier_outlook.sub_messages :

                    #Cette liste de if est nécessaire pour récupérer le corps du message, car il peut être stocké dans l'une des 3 variables marquées ci-dessous en fonction du format de celui-ci
                    if message_courant.html_body is not None :
                        corps_message = message_courant.html_body
                    elif message_courant.plain_text_body is not None :
                        corps_message = message_courant.plain_text_body
                    elif message_courant.rtf_body is not None : 
                        corps_message = message_courant.rtf_body
                    else :
                        corps_message = None

 
                    #Il est obligatoire de passer par une regex analysant l'entête de transport des mails pour récupérer les adresses de réception, puisque la récupération de ces adresses n'est pas gérée par la librairie pypff
                    #Dans le cas où cette entête est vide, il est impossible de récupérer les adresses mails de réception en raison des limitations de la librairie utilisée
                    if message_courant.transport_headers is  None :
                        liste_adresses_mail_reception = None
                        if corps_message is None :
                            print ("Une adresse mail inconnue a envoyé à un ou plusieurs utilisateurs inconnus un mail vide (sans corps) ayant pour objet  [%s]" % (message_courant.subject) )
                        else :
                            print ("Une adresse mail inconnue a envoyé à un ou plusieurs utilisateurs inconnus le mail suivant ayant pour objet  [%s] : %s" % (message_courant.subject,corps_message) )
                    else :
                        resultat_recherche_regex_mail = re.findall(r'(?<!Delivered-)To:[\W<]*([\w+-.%]+@[\w.-]+\.[A-Za-z]{2,4})((,| ,|, | , |){1}[\w+-.%]+@[\w.-]+\.[A-Za-z]{2,4})*>*',message_courant.transport_headers)
                        liste_adresses_mail_reception= []
                        liste_adresses_mail_reception_texte = ""
                        for adresse_mail in resultat_recherche_regex_mail[0] :
                            if len(adresse_mail) > 2 : 
                                liste_adresses_mail_reception.append(adresse_mail.replace(", ",""))
                                liste_adresses_mail_reception_texte = liste_adresses_mail_reception_texte + adresse_mail


                        if corps_message is None :  
                            print ("%s a envoyé aux adresses mails %s un mail vide (sans corps) le %s UTC ayant pour objet  [%s]" % (message_courant.sender_name,liste_adresses_mail_reception_texte, message_courant.delivery_time.strftime("%d-%m-%Y %H:%M:%S"), message_courant.subject) )
                        else :
                            print ("%s a envoyé aux adresses mails %s le mail suivant le %s UTC ayant pour objet  [%s] : %s" % (message_courant.sender_name,liste_adresses_mail_reception_texte, message_courant.delivery_time.strftime("%d-%m-%Y %H:%M:%S"), message_courant.subject,corps_message) )

                    
                    if message_courant.number_of_attachments != 0:

                        try :
                            nom_sous_dossier_dump_piece_jointe = re.sub(r'[^\w\-_\. ]', '_',message_courant.subject) + "-" + str(message_courant.get_delivery_time_as_integer())
                            os.makedirs( dossier_dump / "piece_jointes_dumpes" / nom_sous_dossier_dump_piece_jointe ,exist_ok=True)
                            print ("Ce mail contient %d pièces jointes, qui vont désormais être dumpées" % message_courant.number_of_attachments )
                            i=0
                            for piece_jointe in message_courant.attachments :

                                try :
                                    if piece_jointe.size > shutil.disk_usage(dossier_dump)[1] :
                                        print ("Impossible de dump la pièce jointe numéro %s,car sa taille est supérieure à l'espace restant disponible du dossier de dump")


                                    contenu_piece_jointe = piece_jointe.read_buffer(piece_jointe.size)
                                    with open( dossier_dump / "piece_jointes_dumpes" / nom_sous_dossier_dump_piece_jointe / str(i), 'wb') as dump_piece_jointe :
                                        dump_piece_jointe.write(contenu_piece_jointe)

                                    type_piece_jointe_dumpe = filetype.guess(dossier_dump / "piece_jointes_dumpes" / nom_sous_dossier_dump_piece_jointe / str(i))
                                    if type_piece_jointe_dumpe is None :
                                        print ("La pièce jointe numéro %d, dont le type de fichier est inconnu, a été correctement dumpée" % (i +1))
                                    else :
                                        print ("La pièce jointe numéro %d, qui est un fichier de type %s, a été correctement dumpée" % ((i +1),type_piece_jointe_dumpe.extension))
                                        nouveau_nom_fichier_dumpe = str(i) + "." + type_piece_jointe_dumpe.extension
                                        os.replace(dossier_dump / "piece_jointes_dumpes" / nom_sous_dossier_dump_piece_jointe / str(i),dossier_dump / "piece_jointes_dumpes" / nom_sous_dossier_dump_piece_jointe / nouveau_nom_fichier_dumpe )

                                except  :
                                    print ("Erreur lors du dump de la pièce jointe numéro %s" % (i+ 1))
                                i+=1

                        except  :
                            print ("Erreur lors du dump des pièces jointes")


            if sous_dossier_outlook.get_number_of_sub_folders() != 0 :
                analyse_sous_dossier_outlook(sous_dossier_outlook,liste_sous_dossier_deja_lues,emplacement_dossier_parent + "/" + sous_dossier_outlook.get_name(),dossier_dump)


def analyse_dossier_outlook (chemin_dossier_outlook,partition_windows,dossier_dump,nom_utilisateur,limite_mo_dump_fichier) :

    LISTE_EXTENSIONS_OUTLOOK = [".ost",".pst"]
    is_outlook_data_file_analysed = False

    try :
        contenu_dossier_outlook = partition_windows.open_dir(path=chemin_dossier_outlook)

        for ost_user_file in  contenu_dossier_outlook :
            if ost_user_file.info.meta is not None :

                if ost_user_file.info.meta.type == 1 and os.path.splitext(chemin_dossier_outlook + ost_user_file.info.name.name.decode("utf-8"))[-1].lower() in LISTE_EXTENSIONS_OUTLOOK  :

                    pointeur_fichier_ost = partition_windows.open(path=chemin_dossier_outlook + ost_user_file.info.name.name.decode("utf-8"))
                    resultat_dump_fichier_donnees_outlook = dump_fichier(pointeur_fichier_ost,chemin_dossier_outlook + ost_user_file.info.name.name.decode("utf-8"),dossier_dump,limite_mo_dump_fichier,False)
                    if not resultat_dump_fichier_donnees_outlook :
                        print ("Le dump de fichier de données Outlook %s a échoué." % (chemin_dossier_outlook + ost_user_file.info.name.name.decode("utf-8")) )
                        return(is_outlook_data_file_analysed)
                    pointeur_fichier_ost_dumpe = open(dossier_dump / ost_user_file.info.name.name.decode("utf-8"), "rb")

                    #Les lignes suivantes permettent de tenter de récupérer l'adresse mail de l'utilisateur à partir du nom du fichier Outlook
                    adresse_mail_utilisateur = ost_user_file.info.name.name.decode("utf-8")[:ost_user_file.info.name.name.decode("utf-8").rindex(".")]
                    verification_adresse_mail = re.match(r'\S+@\S+\.\S+$',adresse_mail_utilisateur)
                    if verification_adresse_mail :
                        print ("L'adresse mail de l'utilisateur %s semble être %s" %(nom_utilisateur,adresse_mail_utilisateur))
                    else :
                        print ("Impossible de récupérer l'adresse mail de l'utilisateur %s à partir du nom du fichier de données Outlook" % nom_utilisateur)

                    try :

                        parser_outlook = pypff.file()
                        parser_outlook.open_file_object(pointeur_fichier_ost_dumpe)

                        root_outlook = parser_outlook.get_root_folder()
                        analyse_sous_dossier_outlook(root_outlook,[],"/",dossier_dump)

                        parser_outlook.close()
                        is_outlook_data_file_analysed = True
                        

                    except :
                        print ("L'analyse du fichier de mails stocké à l'emplacement %s a échoué" % chemin_dossier_outlook + ost_user_file.info.name.name.decode("utf-8"))

        return(is_outlook_data_file_analysed)
    except OSError :
        return(is_outlook_data_file_analysed)

def analyse_evt_evtx_securite_windows (pointeur_fichier_evt_ou_evtx_dumpe,software_registry_hive,is_windows_xp) :


    #Ces 3 dictionnaires sont basées sur le lien suivant : https://docs.microsoft.com/fr-fr/windows/security/identity-protection/access-control/security-identifiers
    DICTIONNAIRE_CORRESPONDANCE_GSID_DOMAINE = {"512":"Administrateurs","513":"Utilisateurs","514":"Invités","518":"Administrateurs de schéma","519":"Entreprise Administrateurs","520":"Propriétaire créateurs de stratégie de groupe"}
    DICTIONNAIRE_CORRESPONDANCE_GSID_INTEGRE = {"S-1-5-32-544":"Administrateurs","S-1-5-32-545":"Utilisateurs","S-1-5-32-546":"Invités","S-1-5-32-547":"Utilisateurs avec pouvoir","S-1-5-32-548":"Opérateurs de compte","S-1-5-32-549":"Opérateurs de serveur","S-1-5-32-550":"Opérateurs d'impression","S-1-5-32-551":"Opérateurs de sauvegarde","S-1-5-32-552":"Réplicateurs","S-1-5-32-554":"Pre Windows 2000 Compatible Access","S-1-5-32-555":"RDP","S-1-5-32-556":"Network Configuration Operators","S-1-5-32-557":"Incoming Forest Trust Builders","S-1-5-32-558":"Performance Monitor Users","S-1-5-32-559":"Performance Log Users","S-1-5-32-560":"Windows Authorization Access Group","S-1-5-32-561":"Terminal Server License Servers","S-1-5-32-562":"Distributed COM Users","S-1-5-32-569":"Cryptographic Operators","S-1-5-32-573":"Lecteurs du journal des événements","S-1-5-32-574":"Certificate Service DCOM Access","S-1-5-32-575":"RDS Remote Access Servers","S-1-5-32-576":"RDS Endpoint Servers","S-1-5-32-577":"RDS Management Servers","S-1-5-32-578":"Administrateurs Hyper-V","S-1-5-32-579":"Access Control Assistance Operators","S-1-5-32-580":"Remote Management Users"}
    DICTIONNAIRE_CORRESPONDANCE_SID_UTILISATEUR = {"S-1-5-18":"LocalSystem","S-1-5-19":"LocalService","S-1-5-20":"Service réseau"}

    if is_windows_xp == True :
        if pyevt.check_file_signature_file_object(pointeur_fichier_evt_ou_evtx_dumpe) == False : 
            print ("Le fichier de log de sécurité Windows est corrompu ou invalide, ce qui rend leur analyse impossible")
            return (False)
        fichier_log_securite_windows = pyevt.file()
    else :
        if pyevtx.check_file_signature_file_object(pointeur_fichier_evt_ou_evtx_dumpe) == False : 
            print ("Le fichier de log de sécurité Windows est corrompu ou invalide, ce qui rend leur analyse impossible")
            return (False)
        fichier_log_securite_windows = pyevtx.file()


    fichier_log_securite_windows.open_file_object(pointeur_fichier_evt_ou_evtx_dumpe)

    #Les ID des évènements Windows ainsi que le format des fichiers de log sont différents en fonction de la version de Windows (EVT pour Windows XP et EVTX pour les versions plus récentes)
    if  fichier_log_securite_windows.is_corrupted() :
        print ("Le fichier de log de sécurité Windows est corrompu, ce qui rend leur analyse impossible")
        return(False)
    elif fichier_log_securite_windows.get_number_of_records() == 0:
        print ("Le fichier de log de sécurité Windows est vide. Il est possible que l'enregistrement des évènements de sécurité Windows soit désactivé. C'est le cas par défaut pour les machines Windows XP.")
        return(False)
    else :
        nombre_evenemnt_fichier_evtx =  fichier_log_securite_windows.get_number_of_records()
        i = 0

        if is_windows_xp == True :

            while i < nombre_evenemnt_fichier_evtx :

                evenement_courant_fichier_log =  fichier_log_securite_windows.get_record(i)

                if evenement_courant_fichier_log.get_event_identifier() == 624 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 7 :
                        print ("L'utilisateur %s a créé le compte %s le %s UTC" % (evenement_courant_fichier_log.get_string(3),evenement_courant_fichier_log.get_string(0),evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S")))
                    else :
                        print ("Une création de compte a eu lieu le %s UTC, mais il est impossible de récupérer des informations sur celle-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )

                elif evenement_courant_fichier_log.get_event_identifier() == 626 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 7 :
                        print ("L'utilisateur %s a activé le compte %s le %s UTC" % (evenement_courant_fichier_log.get_string(3),evenement_courant_fichier_log.get_string(0),evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S")))
                    else :
                        print ("Une activation de compte a eu lieu le %s UTC, mais il est impossible de récupérer des informations sur celle-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )

                elif evenement_courant_fichier_log.get_event_identifier() == 628 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 7 :
                        print ("L'utilisateur %s a modifié le mot de passe de %s le %s UTC" % (evenement_courant_fichier_log.get_string(3),evenement_courant_fichier_log.get_string(0),evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S")))
                    else :
                        print ("Une modification de mot de passe a eu lieu le %s UTC, mais il est impossible de récupérer des informations sur celle-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )

                elif evenement_courant_fichier_log.get_event_identifier() == 517 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 6 :
                        print ("ALERTE ! L'utilisateur %s a supprimé les logs de sécurité le %s UTC" % (evenement_courant_fichier_log.get_string(3),evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S")))
                    else :
                        print ("ALERTE ! Une suppression des logs de sécurité a eu lieu le %s UTC, mais il est impossible de récupérer des informations sur l'utilisateur en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )

                elif evenement_courant_fichier_log.get_event_identifier() == 602 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 9 :
                        print ("L'utilisateur %s a créé le %s UTC une tâche programmée exécutant le programme %s avec les droits de l'utilisateur %s" % (evenement_courant_fichier_log.get_string(6), evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S"),evenement_courant_fichier_log.get_string(1),evenement_courant_fichier_log.get_string(5)  ))
                    else :
                        print ("Une tâche programmée a été créée le %s UTC, mais il est impossible de récupérer des informations sur celle-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )

                #Les logs suivants correspondent tous à des échecs de connexion : https://www.ultimatewindowssecurity.com/securitylog/encyclopedia/event.aspx?eventid=4625
                elif evenement_courant_fichier_log.get_event_identifier() == 529 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 6 : 
                        print ("L'utilisateur %s a échoué à se connecter à cause d'une erreur de mot de passe (ou car cet utilisateur n'existe pas) le %s UTC" % (evenement_courant_fichier_log.get_string(0),evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S")))
                    else :
                        print ("Un échec de connexion eu lieu le %s UTC, mais il est impossible de récupérer des informations sur celui-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )

                elif evenement_courant_fichier_log.get_event_identifier() == 530 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 6 : 
                        print ("ALERTE ! L'utilisateur %s UTC a tenté de se connecter en dehors des horaires qui lui ont été définis le %s" % (evenement_courant_fichier_log.get_string(0),evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S")))
                    else :
                        print ("ALERTE ! Un utilisateur a tenté de se connecter en dehors des horaires qui lui ont été définis le %s UTC,mais il est impossible de récupérer des informations sur celui-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )
              
                elif evenement_courant_fichier_log.get_event_identifier() == 531 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 6 : 
                        print ("ALERTE ! L'utilisateur %s a tenté de se connecter le %s UTC alors que son compte était bloqué" % (evenement_courant_fichier_log.get_string(0),evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S")))
                    else :
                        print ("ALERTE ! Un utilisateur a tenté de se connecter alors que son compte était bloqué le %s UTC,mais il est impossible de récupérer des informations sur celui-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )
       
                elif evenement_courant_fichier_log.get_event_identifier() == 532 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 6 : 
                        print ("ALERTE ! L'utilisateur %s a tenté de se connecter le %s UTC alors que son compte était expiré" % (evenement_courant_fichier_log.get_string(0),evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S")))
                    else :
                        print ("ALERTE ! Un utilisateur a tenté de se connecter le %s UTC alors que son compte était expiré,mais il est impossible de récupérer des informations sur celui-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )
                           
                elif evenement_courant_fichier_log.get_event_identifier() == 533 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 6 : 
                        print ("ALERTE ! L'utilisateur %s a tenté de se connecter le %s UTC alors que son compte n'a pas le droit de se connecter à cette machine" % (evenement_courant_fichier_log.get_string(0),evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S")))
                    else :
                        print ("ALERTE ! Un utilisateur a tenté de se connecter alors que son compte n'avait pas le droit de se connecter à cette machine le %s UTC,mais il est impossible de récupérer des informations sur celui-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )
                           
                elif evenement_courant_fichier_log.get_event_identifier() == 535 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 6 : 
                        print ("L'utilisateur %s a tenté de se connecter avec un mot de passe expiré le %s UTC" % (evenement_courant_fichier_log.get_string(0), evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") ))
                    else :
                        print ("Un utilisateur a tenté de se connecter avec un mot de passe expiré le %s UTC,mais il est impossible de récupérer des informations sur celui-ci en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )
       
                elif evenement_courant_fichier_log.get_event_identifier() == 537 :

                    if evenement_courant_fichier_log.get_number_of_strings() == 6 : 
                        print ("L'utilisateur %s a échoué à se connecter le %s UTC pour une raison inconnue" % (evenement_courant_fichier_log.get_string(0), evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") ))
                    else :
                        print ("Un échec de connexion utilsiateur pour une raison inconnue a eu lieu le %s UTC,mais il est impossible de récupérer des informations sur le compte en question en raison d'une erreur d'enregistrement de logs" % evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S") )

                i += 1 

        else :

            while i < nombre_evenemnt_fichier_evtx :

                evenement_courant_fichier_log =  fichier_log_securite_windows.get_record(i)

                if evenement_courant_fichier_log.get_event_identifier() == 4720 :

                    evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_log.get_xml_string())

                    if evtx_to_xml[1][5].text is not None :

                        print ("L'utilisateur %s du domaine %s a été créé le %s UTC" % (evtx_to_xml[1][0].text,evtx_to_xml[1][5].text,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))
                        
                elif evenement_courant_fichier_log.get_event_identifier() == 4722 :

                    evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_log.get_xml_string())

                    print ("L'utilisateur %s du domaine %s a été activé le %s UTC" % (evtx_to_xml[1][0].text,evtx_to_xml[1][5].text,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))

                elif evenement_courant_fichier_log.get_event_identifier() == 4724 :

                    evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_log.get_xml_string())

                    print ("Le mot de passe de l'utilisateur %s du domaine %s a été modifié le %s UTC" % (evtx_to_xml[1][0].text,evtx_to_xml[1][5].text,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))

                elif evenement_courant_fichier_log.get_event_identifier() == 4728 :

                    evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_log.get_xml_string())

                    SID_utilisateur_evtx =  evtx_to_xml[1][1].text

                    if software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList').get_subkey(SID_utilisateur_evtx,raise_on_missing=False) is not None :

                        emplacement_compte_utilisateur = software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList').get_subkey(SID_utilisateur_evtx,raise_on_missing=False).get_value(value_name="ProfileImagePath")
                        nom_utilisateur = emplacement_compte_utilisateur[(emplacement_compte_utilisateur.rindex("\\") +1):]
                        SID_groupe_evtx = evtx_to_xml[1][4].text[(evtx_to_xml[1][4].text.rindex("-")+1):]

                        if DICTIONNAIRE_CORRESPONDANCE_GSID_DOMAINE.get(SID_groupe_evtx) is  None:
                            print ("L'utilisateur %s a été ajouté au groupe ayant le SID %s (nom inconnu) du domaine %s le %s UTC" % (nom_utilisateur,SID_groupe_evtx,evtx_to_xml[1][7].text,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))
                        else: 
                            for groupe_SID,description_groupe_SID in DICTIONNAIRE_CORRESPONDANCE_GSID_DOMAINE.items() :
                                if groupe_SID == SID_groupe_evtx :
                                    print ("L'utilisateur %s a été ajouté au groupe %s du domaine %s le %s UTC" % (nom_utilisateur,description_groupe_SID,evtx_to_xml[1][7].text,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))

                elif evenement_courant_fichier_log.get_event_identifier() == 4732 : 
                
                    evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_log.get_xml_string())

                    SID_utilisateur_evtx =  evtx_to_xml[1][1].text

                    if software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList').get_subkey(SID_utilisateur_evtx,raise_on_missing=False) is not None :

                        emplacement_compte_utilisateur = software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList').get_subkey(SID_utilisateur_evtx,raise_on_missing=False).get_value(value_name="ProfileImagePath")
                        nom_utilisateur = emplacement_compte_utilisateur[(emplacement_compte_utilisateur.rindex("\\") +1):]
                        nom_groupe_evtx = evtx_to_xml[1][2].text

                        print ("L'utilisateur %s a été ajouté au groupe local %s le %s UTC" % (nom_utilisateur,nom_groupe_evtx,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))
            

                elif evenement_courant_fichier_log.get_event_identifier() == 1102 :
                
                    evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_log.get_xml_string())
                    print ("ATTENTION ! L'utilisateur %s a supprimé les logs de sécurité Windows le %s UTC" % (evtx_to_xml[1][0][1].text, evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f") ))

                elif evenement_courant_fichier_log.get_event_identifier() == 4625 :
                
                    evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_log.get_xml_string())
                    print ("L'utilisateur %s a essayé de se connecter sans succès le %s UTC" % (evtx_to_xml[1][5].text,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))

            #Le stockage de logs pour ce type d'évènements nécessite une modification de la stratégie de gestion des logs Windows : https://www.csoonline.com/article/3373498/how-to-audit-windows-task-scheduler-for-cyber-attack-activity.html

                elif evenement_courant_fichier_log.get_event_identifier() == 4698 :
                
                    evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_log.get_xml_string())
                    SID_utilisateur_evtx =  evtx_to_xml[1][0].text

                    if SID_utilisateur_evtx in DICTIONNAIRE_CORRESPONDANCE_SID_UTILISATEUR.keys()   :
                        nom_utilisateur = DICTIONNAIRE_CORRESPONDANCE_SID_UTILISATEUR[SID_utilisateur_evtx]
                    elif software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList').get_subkey(SID_utilisateur_evtx,raise_on_missing=False) is not None :

                        emplacement_compte_utilisateur = software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList').get_subkey(SID_utilisateur_evtx,raise_on_missing=False).get_value(value_name="ProfileImagePath")
                        nom_utilisateur = emplacement_compte_utilisateur[(emplacement_compte_utilisateur.rindex("\\") +1):]
                    else :
                        nom_utilisateur = None
                
                    try :

                        description_scheduled_task_xml = xml.etree.ElementTree.fromstring(evtx_to_xml[1][5].text)

                        try :
                            programme_tache_planifiee = description_scheduled_task_xml[3][0][0].text + " " +  description_scheduled_task_xml[3][0][1].text
                        except :
                            programme_tache_planifiee = description_scheduled_task_xml[4][0][0].text + " " +  description_scheduled_task_xml[4][0][1].text

                        if nom_utilisateur is None :
                            print ("L'utilisateur inconnu ou supprimé ayant le SID %s a créé une tâche planifiée le %s UTC exécutant le programme suivant : %s" % (SID_utilisateur_evtx,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f"),programme_tache_planifiee ))
                        else :
                            print ("L'utilisateur %s a créé une tâche planifiée le %s exécutant le programme suivant : %s UTC" % (nom_utilisateur,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f"),programme_tache_planifiee ))
                    except :

                        if nom_utilisateur is None :
                            print ("L'utilisateur inconnu ou supprimé ayant le SID %s a créé une tâche planifiée le %s UTC, mais il est impossible de récupérer les informations sur le programme lancé par celle-ci" % (SID_utilisateur_evtx,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))
                        else :
                            print ("L'utilisateur %s a créé une tâche planifiée le %s UTC, mais il est impossible de récupérer les informations sur le programme lancé par celle-ci " % (nom_utilisateur,evenement_courant_fichier_log.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))


                i += 1 

def analyse_partition_systeme_windows (partition_windows,limite_mo_dump_fichier,dossier_dump) :

  
  try:

    #Dump et analyse des fichiers de registre Windows
    for fichier_registre in ["SAM","SYSTEM","SOFTWARE"] :
      file_entry = partition_windows.open("Windows/System32/Config/" + fichier_registre)
      resultat_dump_fichier_registre = dump_fichier(file_entry,"Windows/System32/Config/" + fichier_registre,dossier_dump,limite_mo_dump_fichier,True)
      if not resultat_dump_fichier_registre :
          print ("ALERTE ! Le dump du fichier registre %s a échoué, alors que l'analyse de ce dernier est indispensable au bon fonctionnement de ce script" %resultat_dump_fichier_registre)

    system_registry_hive   = regipy.registry.RegistryHive(dossier_dump / "SYSTEM")
    software_registry_hive = regipy.registry.RegistryHive(dossier_dump / "SOFTWARE")

    #Récupération du numéro du Current Control Set, qui est la clé registre Système utilisée actuellement par la machine (les autres clés CurrentSet étant des sauvegardes)
    numero_control_set = str(system_registry_hive.get_key('SYSTEM\Select').get_value(value_name="Current")).zfill(3)

    #Récupération du nom de la machine depuis le Registre 
    nom_machine = system_registry_hive.get_key('SYSTEM\ControlSet' + numero_control_set +'\Control\ComputerName\ComputerName').get_value(value_name="ComputerName")
    print ("Le nom de la machine dumpée est %s" %nom_machine)


    #Récupération du numéro de build et de la version de l'OS depuis le Registre 
    build_version_machine = software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion').get_value(value_name="CurrentBuildNumber")
    product_name_machine = software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion').get_value(value_name="ProductName")
    print ("La machine dumpée est une machine %s build %s" % (product_name_machine,build_version_machine))

    if product_name_machine == "Microsoft Windows XP" :
        is_windows_xp = True
    else :
        is_windows_xp = False

    #Récupération depuis le Registre Software de la liste des programmes s'exécutant automatiquement au démarrage de l'ordinateur
    print ("Voici la liste des applications exécutées automatiquement au démarrage de la machine  : \n" )
    for nom_programme in software_registry_hive.get_key('Software\Microsoft\Windows\CurrentVersion\Run').iter_values() :
        print (" %s : %s" % (nom_programme.name,nom_programme.value)) 
    for nom_programme in software_registry_hive.get_key('Software\Microsoft\Windows\CurrentVersion\RunOnce').iter_values() :
        print (" %s : %s" % (nom_programme.name,nom_programme.value)) 
    try:
        for nom_programme in software_registry_hive.get_key('Software\Microsoft\Windows\CurrentVersion\policies\Explorer\Run').iter_values() :
            print (" %s : %s" % (nom_programme.name,nom_programme.value)) 
    except: 
        pass

    #Analyse des valeurs Shell et Userinit de la clé de registre SOFTWARE/MICROSOFT/WINDOWS NT/CURRENT VERSION/WINLOGON 
    shell_winlogon_software_registry = software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\Winlogon').get_value(value_name="Shell")
    if shell_winlogon_software_registry != "explorer.exe" and shell_winlogon_software_registry != "Explorer.exe" :
        print ("ALERTE ! La valeur shell de la clé Winlogon est %s" % shell_winlogon_software_registry)
    else :
        print ("La valeur Shell de la clé Winlogon est correcte")
    userinit_winlogon_software_registry = software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\Winlogon').get_value(value_name="Userinit")
    if (re.search(r"^C:\\Windows\\system32\\userinit\.exe", userinit_winlogon_software_registry) is None and is_windows_xp == False) or (re.search(r"^C:\\WINDOWS\\system32\\userinit\.exe", userinit_winlogon_software_registry) is None and is_windows_xp == True) :
        print ("ALERTE ! La valeur shell de la clé Winlogon est %s" % userinit_winlogon_software_registry)
    else :
        print ("La valeur Userinit de la clé Winlogon est correcte")
   

    #Récupération de la liste des périphériques USB depuis le Registre SYSTEM
    nombre_peripherique_usb_machine = 0
    dictionnaire_peripherique_usb_machine = {}

    #Ce if permet de vérifier que la sous-clé contenant les informations des périphériques de stockage USB existe
    if system_registry_hive.get_key("SYSTEM\ControlSet" + numero_control_set +"\Enum").get_subkey("USBSTOR",raise_on_missing=False) is not None :
      for peripherique_usb_machine in system_registry_hive.get_key("SYSTEM\ControlSet" + numero_control_set +"\Enum\\USBSTOR").iter_subkeys():
        nombre_peripherique_usb_machine += 1
        ugly_name_peripherique_usb_machine = peripherique_usb_machine.name
        for sub_folder_peripherique_usb_machine in system_registry_hive.get_key("SYSTEM\ControlSet" + numero_control_set + "\Enum\\USBSTOR\\" + ugly_name_peripherique_usb_machine).iter_subkeys():
          dictionnaire_peripherique_usb_machine[ugly_name_peripherique_usb_machine] = system_registry_hive.get_key("SYSTEM\ControlSet" + numero_control_set + "\Enum\\USBSTOR\\" + ugly_name_peripherique_usb_machine + "\\" + sub_folder_peripherique_usb_machine.name).get_value(value_name="FriendlyName")

      if nombre_peripherique_usb_machine > 0 and is_windows_xp == False :
        print ("%d périphérique(s) USB ont déjà été connectés à la machine dumpée : \n" % nombre_peripherique_usb_machine )
        for ID_peripherique_USB,nom_peripherique_usb in dictionnaire_peripherique_usb_machine.items() :
        
          for sub_folder_peripherique_usb_machine in system_registry_hive.get_key("SYSTEM\ControlSet" + numero_control_set + "\Enum\\USBSTOR\\" + ID_peripherique_USB).iter_subkeys():
              
              date_derniere_deconnexion_cle_usb = None
              for sous_cle_information_date_cle_usb in system_registry_hive.get_key('SYSTEM\ControlSet' + numero_control_set +'\Enum\\USBSTOR\\' + ID_peripherique_USB + '\\' + sub_folder_peripherique_usb_machine.name + '\Properties\{83da6326-97a6-4088-9453-a1923f573b29}').iter_subkeys() :
                  if sous_cle_information_date_cle_usb.name == "0064" : 
                      date_premiere_connexion_cle_usb = regipy.registry.convert_wintime(sous_cle_information_date_cle_usb.header.last_modified).strftime("%d %B %Y %H:%M:%S")
                  elif sous_cle_information_date_cle_usb.name == "0066" :
                      date_derniere_connexion_cle_usb = regipy.registry.convert_wintime(sous_cle_information_date_cle_usb.header.last_modified).strftime("%d %B %Y %H:%M:%S")
                  elif sous_cle_information_date_cle_usb.name == "0067" :
                      date_derniere_deconnexion_cle_usb = regipy.registry.convert_wintime(sous_cle_information_date_cle_usb.header.last_modified).strftime("%d %B %Y %H:%M:%S")

        #Il n'y a pas de  sous-clé indiquant la date de dernière déconnexion de la clé USB dans le cas où la clé USB n'a jamais été déconnectée pendant que l'ordinateur était allumé 
        if date_derniere_deconnexion_cle_usb is not None :
            print ("  %s, connecté pour la 1ère fois le %s et la dernière fois le %s, et déconnecté pour la dernière fois le %s\n" % (nom_peripherique_usb,date_premiere_connexion_cle_usb,date_derniere_connexion_cle_usb,date_derniere_deconnexion_cle_usb))
        else :
            print ("  %s, connecté pour la 1ère fois le %s et la dernière fois le %s\n" % (nom_peripherique_usb,date_premiere_connexion_cle_usb,date_derniere_connexion_cle_usb))

      elif nombre_peripherique_usb_machine > 0 and is_windows_xp == True :
          print ("%d périphérique(s) USB ont déjà été connectés à la machine dumpée : \n" % nombre_peripherique_usb_machine )

          for _,nom_peripherique_usb in dictionnaire_peripherique_usb_machine.items() :
            print (" %s" % nom_peripherique_usb )

      else :
        print ("Aucun périphérique USB n'a été connecté sur la machine dumpée\n")
    else:
        print ("Aucun périphérique USB n'a été connecté sur la machine dumpée\n")


    #Analyse du pare-feu Windows
    if is_windows_xp == True :
        print ("Impossible de récupérer des informations concernant l'activation du pare-feu pour les machines Windows XP")
    else :
        is_domain_firewall_activated = system_registry_hive.get_key('SYSTEM\ControlSet' + numero_control_set + '\Services\SharedAccess\Parameters\FirewallPolicy\DomainProfile').get_value(value_name="EnableFirewall")
        is_public_firewall_activated = system_registry_hive.get_key('SYSTEM\ControlSet' + numero_control_set + '\Services\SharedAccess\Parameters\FirewallPolicy\PublicProfile').get_value(value_name="EnableFirewall")
        is_standard_firewall_activated = system_registry_hive.get_key('SYSTEM\ControlSet' + numero_control_set + '\Services\SharedAccess\Parameters\FirewallPolicy\StandardProfile').get_value(value_name="EnableFirewall")

        if is_domain_firewall_activated == 1 :
            print ("Le pare-feu est activé lorsque l'ordinateur est connecté à un réseau où est installé l'AD utilisé par cette machine")
        else :
            print ("ALERTE ! Le pare-feu est désactivé lorsque l'ordinateur est connecté à un réseau où est installé l'AD utilisé par cette machine")
        if is_public_firewall_activated == 1 :
            print ("Le pare-feu est activé lorsque l'ordinateur est connecté à un réseau public")
        else : 
            print ("ALERTE ! Le pare-feu est désactivé lorsque l'ordinateur est connecté à un réseau public")
        if is_standard_firewall_activated == 1 :
            print ("Le pare-feu est activé lorsque l'ordinateur est connecté à un réseau standard (à la maison par exemple)")
        else :
            print ("ALERTE ! Le pare-feu est désactivé lorsque l'ordinateur est connecté à un réseau standard (à la maison par exemple)")

    #Récupération de la version d'Office s'il est installé (permettra de désactiver l'analyse des fichiers PST/OST dans la partie utilisateur)
    #La version d'Office installée sur la machine est stockée sous la ferme d'un nombre flottant. Ce dictionnaire permet de faire correspondre ce nombre au nom de la version installée
    DICTIONNAIRE_CORRESPODNANCE_VERSION_OFFICE = {7.0:"97",8.0:"98",9.0:"2000",10.0:"XP",11.0:"2003",12.0:"2007",14.0:"2010",15.0:"2013",16.0:"2016 ou 2019"}
    numero_version_outlook = 0
    
    try :
        for sous_cle_registre_office in software_registry_hive.get_key('SOFTWARE\Microsoft\Office').iter_subkeys() :
            try:
                if float(sous_cle_registre_office.name) > numero_version_outlook :
                    numero_version_outlook = float(sous_cle_registre_office.name)
            except ValueError :
                pass

        if numero_version_outlook in DICTIONNAIRE_CORRESPODNANCE_VERSION_OFFICE.keys() :
            print ("Microsoft Office %s est installé sur cette machine" % DICTIONNAIRE_CORRESPODNANCE_VERSION_OFFICE[numero_version_outlook] )
        elif numero_version_outlook != 0 :
            print ("Une version inconnue par ce script de Microsoft Office est installée sur cette machine")
        is_office_installed = True
    #Evite une erreur du script dans le cas où la clé Office n'existe pas (c'est le cas par exemple si Office n'est pas installé sur la machine)
    except regipy.RegistryKeyNotFoundException :
        pass
    if numero_version_outlook == 0 :
        is_office_installed = False
        print ("Microsoft Office n'est pas installé sur cette machine")


    #Création d'un dictionnaire contenant la liste des comptes utilisateurs de la machine (nécessaire pour analyser les fichiers NtUser.Dat de ces mêmes utilisateurs) et l'emplacement de chacun d'entre eux
    dictionnaire_utilisateur = {}
    for sous_cle_id_compte in software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList').iter_subkeys():
        if sous_cle_id_compte.name[0:9] == "S-1-5-21-" :
            emplacement_compte_utilisateur = software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList\\' + sous_cle_id_compte.name ).get_value(value_name="ProfileImagePath")        
            emplacement_compte_utilisateur = emplacement_compte_utilisateur[(emplacement_compte_utilisateur.index("\\") +1):].replace("\\","/")
            nom_utilisateur = emplacement_compte_utilisateur[(emplacement_compte_utilisateur.rindex("/") +1):]
            dictionnaire_utilisateur[nom_utilisateur] = emplacement_compte_utilisateur

    #Analyse du fichier NTUSER.DAT pour chaque utilisateur 
    for utilisateur,emplacement_utilisateur in dictionnaire_utilisateur.items():

        file_entry = partition_windows.open(emplacement_utilisateur + "/NTUSER.DAT")
        resultat_dump_ntuser = dump_fichier(file_entry,emplacement_utilisateur + "/NTUSER.DAT",dossier_dump,limite_mo_dump_fichier,True)
        if not resultat_dump_ntuser :
            print ("Le dump du fichier NTUSER.DAT de l'utilisateur %s a échoué. Les informations concernant ce compte ne seront donc pas analysés par ce script" % utilisateur )
            continue

        user_registry_hive = regipy.registry.RegistryHive(dossier_dump / "NTUSER.DAT")

        #Affichage de la liste des applications exécutées automatiquement au démarrage des sessions utilisateurs
        if user_registry_hive.get_key("NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion").get_subkey("Run",raise_on_missing=False) is None and user_registry_hive.get_key("NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion").get_subkey("RunOnce",raise_on_missing=False) is None : 
            print ("Aucune application n'est exécutée automatiquement au démarrage de la session de l'utilisateur %s \n" % utilisateur)
        elif user_registry_hive.get_key("NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion").get_subkey("Run",raise_on_missing=False) is not None and user_registry_hive.get_key("NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion").get_subkey("RunOnce",raise_on_missing=False) is  None : 
            nombre_cle_run_user = len(user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\Run').get_values())
            if nombre_cle_run_user != 0 : 
                print ("Voici la liste des applications exécutées automatiquement au démarrage de la session de l'utilisateur %s : \n" % utilisateur )
                for sous_cle_id_compte in user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\Run').iter_values() :
                    print (" %s : %s" % (sous_cle_id_compte.name,sous_cle_id_compte.value))
            else:
                print ("Aucune application n'est exécutée automatiquement au démarrage de la session de l'utilisateur %s \n" % utilisateur)
        elif user_registry_hive.get_key("NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion").get_subkey("Run",raise_on_missing=False) is None and user_registry_hive.get_key("NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion").get_subkey("RunOnce",raise_on_missing=False) is not None : 
            nombre_cle_runonce_user = len(user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\RunOnce').get_values())
            if nombre_cle_runonce_user != 0 : 
                print ("Voici la liste des applications exécutées automatiquement au démarrage de la session de l'utilisateur %s : \n" % utilisateur )
                for sous_cle_id_compte in user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\RunOnce').iter_values() :
                    print (" %s : %s" % (sous_cle_id_compte.name,sous_cle_id_compte.value))
            else:
                print ("Aucune application n'est exécutée automatiquement au démarrage de la session de l'utilisateur %s \n" % utilisateur)
        else:
            nombre_cle_run_user = len(user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\Run').get_values())
            nombre_cle_runonce_user = len(user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\RunOnce').get_values())
            if nombre_cle_run_user != 0 and nombre_cle_runonce_user == 0 :
                print ("Voici la liste des applications exécutées automatiquement au démarrage de la session de l'utilisateur %s : \n" % utilisateur )
                for sous_cle_id_compte in user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\Run').iter_values() :
                    print (" %s : %s" % (sous_cle_id_compte.name,sous_cle_id_compte.value))
            elif nombre_cle_run_user == 0 and nombre_cle_runonce_user != 0 :
                print ("Voici la liste des applications exécutées automatiquement au démarrage de la session de l'utilisateur %s : \n" % utilisateur )
                for sous_cle_id_compte in user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\RunOnce').iter_values() :
                    print (" %s : %s" % (sous_cle_id_compte.name,sous_cle_id_compte.value))
            elif nombre_cle_run_user != 0 and nombre_cle_runonce_user != 0 :
                print ("Voici la liste des applications exécutées automatiquement au démarrage de la session de l'utilisateur %s : \n" % utilisateur )
                for sous_cle_id_compte in user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\Run').iter_values() :
                    print (" %s : %s" % (sous_cle_id_compte.name,sous_cle_id_compte.value))
                for sous_cle_id_compte in user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\RunOnce').iter_values() :
                    print (" %s : %s" % (sous_cle_id_compte.name,sous_cle_id_compte.value))
            else :
                print ("Aucune application n'est exécutée automatiquement au démarrage de la session de l'utilisateur %s \n" % utilisateur)
        
        #Analyse des fichiers lnk correspondant aux fichiers récemment lus ou exécutés par un utilisateur (le format lnk étant utilisé pour les raccourcis sur Windows)
        if is_windows_xp == False :
            emplacement_dossier_fichier_recent = emplacement_utilisateur + "/AppData/Roaming/Microsoft/Windows/Recent"
        else :
            emplacement_dossier_fichier_recent = emplacement_utilisateur + "/Recent"
        contenu_dossier_lnk_fichier_recent = partition_windows.open_dir(path=emplacement_dossier_fichier_recent)
        for fichier_lnk  in contenu_dossier_lnk_fichier_recent :
            if fichier_lnk.info.meta.type == 1 and ".lnk" == fichier_lnk.info.name.name.decode("utf-8")[-4:] :

                pointeur_fichier_lnk = partition_windows.open(emplacement_dossier_fichier_recent + "/"  + fichier_lnk.info.name.name.decode("utf-8") )
                resultat_dump_lnk = dump_fichier(pointeur_fichier_lnk,emplacement_utilisateur + "/"  + fichier_lnk.info.name.name.decode("utf-8"),dossier_dump,limite_mo_dump_fichier,False)
                if not resultat_dump_lnk :
                    print ("Le dump du fichier .lnk %s a échoué. Il ne sera donc pas analysé par ce script" % (emplacement_utilisateur + "/"  + fichier_lnk.info.name.name.decode("utf-8")) )
                    continue

                with open(dossier_dump / fichier_lnk.info.name.name.decode("utf-8"), 'rb') as data_lnk:

                    lnk = LnkParse3.lnk_file(data_lnk)
                    json_lnk = lnk.get_json()

                    if str(json_lnk["header"]["creation_time"]) != "None" and json_lnk["header"]["file_flags"][0] != "FILE_ATTRIBUTE_DIRECTORY" :

                        if "local_base_path" not in json_lnk["link_info"] :
                            print ("Le raccourci %s ne point pas sur un fichier stocké en local sur la machine" % fichier_lnk.info.name.name.decode("utf-8"))
                        else :
                            destination_fichier_lnk = json_lnk["link_info"]["local_base_path"] + json_lnk["link_info"]["common_path_suffix"]
                            is_local_or_network_lnk = json_lnk["link_info"]["location"]
                            if is_local_or_network_lnk != "Local" :
                                print ("Le raccourci %s ne point pas sur un fichier stocké en local sur la machine" % fichier_lnk.info.name.name.decode("utf-8"))
                            elif destination_fichier_lnk[:3] != "C:\\" and is_local_or_network_lnk == "Local"  :
                                print ("Le fichier pointé par le raccourci %s est stocké sur une autre partition que la partition système" % fichier_lnk.info.name.name.decode("utf-8"))
                            else :                            
                                destination_fichier_lnk = destination_fichier_lnk[3:].replace("\\","/")
                                #Cette vérification permet d'éviter que le script crashe dans le cas où il essaye de dumper un fichier déjà supprimé
                                try :
                                    pointeur_destination_fichier_lnk = partition_windows.open(destination_fichier_lnk )
                                    dump_fichier(pointeur_destination_fichier_lnk,destination_fichier_lnk,dossier_dump,limite_mo_dump_fichier,False)
                                    print ("Le fichier %s, qui a été récemment lu par l'utilisateur %s, a été correctement dumpé" % (destination_fichier_lnk,utilisateur) )
                                except OSError :
                                    print ("Le fichier %s, qui a été récemment lu par l'utilisateur %s, a été supprimé avant la réalisation de ce dump disque" % (destination_fichier_lnk,utilisateur) )

        #Dump du fichier d'historique Powershell
        if is_windows_xp == False :
            try :

                pointeur_historique_powershell = partition_windows.open(path=emplacement_utilisateur + "/AppData/Roaming/Microsoft/Windows/Powershell/PSReadline/ConsoleHost_history.txt")
                resultat_dump_historique_powershell = dump_fichier(pointeur_historique_powershell,emplacement_utilisateur + "/AppData/Roaming/Microsoft/Windows/Powershell/PSReadline/ConsoleHost_history.txt",dossier_dump,limite_mo_dump_fichier,False)
                if not resultat_dump_historique_powershell :
                    print ("Le dump de l'historique Powershell de l'utilisateur %s a échoué" %utilisateur) 
                else :
                    with open(dossier_dump / "ConsoleHost_history.txt", 'r') as data_historique_powershell:

                        print ("Voici l'historique des commandes Powershell lancées par l'utilisateur %s. La dernière d'entre elles a été exécutée le %s.\n" % (utilisateur,datetime.datetime.fromtimestamp(pointeur_historique_powershell.info.meta.ctime)))
                        print (data_historique_powershell.read())

            except :
                print ("Aucun historique de commandes Powershell n'est disponible pour l'utilisateur %s" % utilisateur)
        

        #Les fichiers de données Outlook sont stockés dans un emplacement différent en fonction de la version d'Outlook et de Windows : https://www.stellarinfo.com/article/find-change-pst-file-location-outlook-windows.php
        if is_office_installed == True :
            if numero_version_outlook == 10.0 or numero_version_outlook == 11.0 or numero_version_outlook == 12.0 :
                resultat_analyse_outlook = analyse_dossier_outlook(emplacement_utilisateur + "/Local Settings/Application Data/Microsoft/Outlook/",partition_windows,dossier_dump,utilisateur,limite_mo_dump_fichier)
                if resultat_analyse_outlook == False :
                    resultat_analyse_outlook = analyse_dossier_outlook(emplacement_utilisateur + "/AppData/Local/Microsoft/Outlook/",partition_windows,dossier_dump,utilisateur,limite_mo_dump_fichier)


            elif numero_version_outlook == 14.0 and is_windows_xp == True :

                emplacement_dossier_mes_documents = user_registry_hive.get_key('NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\Explorer\\User Shell Folders').get_value(value_name="Personal")
                emplacement_dossier_mes_documents = emplacement_utilisateur + emplacement_dossier_mes_documents[emplacement_dossier_mes_documents.index('\\'):].replace("\\","/")

                resultat_analyse_outlook = False
                contenu_dossier_mes_documents = partition_windows.open_dir(path=emplacement_dossier_mes_documents)
                for objet_mes_documents in contenu_dossier_mes_documents :

                    if objet_mes_documents.info.meta.type == 2 and (objet_mes_documents.info.name.name.decode("utf-8") != "." and objet_mes_documents.info.name.name.decode("utf-8") != ".." ):
                        sous_dossier_mes_documents = emplacement_dossier_mes_documents + "/" + objet_mes_documents.info.name.name.decode("utf-8") + "/"
                        resultat_analyse_outlook = analyse_dossier_outlook(sous_dossier_mes_documents,partition_windows,dossier_dump,utilisateur,limite_mo_dump_fichier)
                        
                    if resultat_analyse_outlook :
                        break

            else : 
                resultat_analyse_outlook = analyse_dossier_outlook(emplacement_utilisateur + "/AppData/Local/Microsoft/Outlook/",partition_windows,dossier_dump,utilisateur,limite_mo_dump_fichier)

            if resultat_analyse_outlook == False : 
                print ("L'utilisateur %s n'utilise pas le client lourd Outlook (ou le dump de son fichier de données Outlook a échoué)" % utilisateur)


    #Analyse des logs Sécurité Windows
    if is_windows_xp == False :
        emplacement_fichier_log_evtx_securite = system_registry_hive.get_key('SYSTEM\ControlSet' + numero_control_set + '\services\eventlog\Security').get_value(value_name="File").replace("%SystemRoot%","Windows").replace("\\","/")
    else :
        emplacement_fichier_log_evtx_securite = system_registry_hive.get_key('SYSTEM\ControlSet' + numero_control_set + '\services\eventlog\Security').get_value(value_name="File").replace("%SystemRoot%","WINDOWS").replace("\\","/")

    pointeur_fichier_log_evtx_securite = partition_windows.open(emplacement_fichier_log_evtx_securite )
    resultat_dump_log_securite = dump_fichier(pointeur_fichier_log_evtx_securite,emplacement_fichier_log_evtx_securite,dossier_dump,limite_mo_dump_fichier,True)
    if not resultat_dump_log_securite :
        print ("Le dump de fichier de log des évènements de sécurité Windows a échoué")
    else :
        nom_fichier_log_evtx_securite =  emplacement_fichier_log_evtx_securite[(emplacement_fichier_log_evtx_securite.rindex("/") +1):]
        pointeur_fichier_evtx_dumpe = open(dossier_dump / nom_fichier_log_evtx_securite, "rb")
        analyse_evt_evtx_securite_windows(pointeur_fichier_evtx_dumpe,software_registry_hive,is_windows_xp)
    
      
    #Analyse des logs Système Windows
    DICTIONNAIRE_CORRESPONDANCE_SID_UTILISATEUR = {"S-1-5-18":"LocalSystem","S-1-5-19":"LocalService","S-1-5-20":"Service réseau"}
    if is_windows_xp == True : 
        print ("L'analyse des logs Système n'est pas activée pour Windows XP")

    else :
        emplacement_fichier_log_evtx_systeme = system_registry_hive.get_key('SYSTEM\ControlSet' + numero_control_set + '\services\eventlog\System').get_value(value_name="File").replace("%SystemRoot%","Windows").replace("\\","/")
        pointeur_fichier_log_evtx_systeme = partition_windows.open(emplacement_fichier_log_evtx_systeme )
        resultat_dump_fichier_systeme = dump_fichier(pointeur_fichier_log_evtx_systeme,emplacement_fichier_log_evtx_systeme,dossier_dump,limite_mo_dump_fichier,True)
        if not resultat_dump_fichier_systeme :
            print ("Le dump de fichier de log des évènements système Windows a échoué")
        else: 

            nom_fichier_log_evtx_securite =  emplacement_fichier_log_evtx_systeme[(emplacement_fichier_log_evtx_systeme.rindex("/") +1):]
            pointeur_fichier_evtx_dumpe = open(dossier_dump / nom_fichier_log_evtx_securite, "rb")
            evtx_file = pyevtx.file()
            evtx_file.open_file_object(pointeur_fichier_evtx_dumpe)


            if evtx_file.is_corrupted() :
                print ("Le fichier EVTX correspondant aux logs système Windows est corrompu, ce qui rend leur analyse impossible")
            else :
                nombre_evenemnt_fichier_evtx =  evtx_file.get_number_of_records()
                i = 0

                while i < nombre_evenemnt_fichier_evtx :

                    evenement_courant_fichier_evtx =  evtx_file.get_record(i)
                    if evenement_courant_fichier_evtx.get_event_identifier() == 7045 :

                        evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_evtx.get_xml_string())

                        if  evtx_to_xml[1][4].text is None :
                            nom_compte_service = "LocalSystem"
                        else : 
                            nom_compte_service = evtx_to_xml[1][4].text

                        SID_utilisateur_evtx =  evtx_to_xml[0][13].attrib["UserID"]

                        if SID_utilisateur_evtx  in DICTIONNAIRE_CORRESPONDANCE_SID_UTILISATEUR.keys() :

                            print ("Le service %s de type %s, stocké à l'emplacement %s et qui sera exécuté par l'utilisateur %s, a été installé par l'utilisateur %s le %s UTC (ce service démarre de la manière suivante : %s)" %(evtx_to_xml[1][0].text,evtx_to_xml[1][2].text,evtx_to_xml[1][1].text,nom_compte_service,DICTIONNAIRE_CORRESPONDANCE_SID_UTILISATEUR[SID_utilisateur_evtx],evenement_courant_fichier_evtx.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f"),evtx_to_xml[1][3].text))

                        elif software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList').get_subkey(SID_utilisateur_evtx,raise_on_missing=False) is not None :


                            emplacement_compte_utilisateur = software_registry_hive.get_key('Software\Microsoft\Windows Nt\CurrentVersion\ProfileList').get_subkey(SID_utilisateur_evtx,raise_on_missing=False).get_value(value_name="ProfileImagePath")
                            nom_utilisateur = emplacement_compte_utilisateur[(emplacement_compte_utilisateur.rindex("\\") +1):]

                            print ("Le service %s de type %s, stocké à l'emplacement %s et qui sera exécuté par l'utilisateur %s, a été installé par l'utilisateur %s le %s UTC (ce service démarre de la manière suivante : %s)" %(evtx_to_xml[1][0].text,evtx_to_xml[1][2].text,evtx_to_xml[1][1].text,nom_compte_service,nom_utilisateur,evenement_courant_fichier_evtx.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f"),evtx_to_xml[1][3].text))

                        else :
                            print ("Le service %s de type %s, stocké à l'emplacement %s et qui sera exécuté par l'utilisateur ayant le SID %s, a été installé par l'utilisateur %s le %s UTC (ce service démarre de la manière suivante : %s)" %(evtx_to_xml[1][0].text,evtx_to_xml[1][2].text,evtx_to_xml[1][1].text,nom_compte_service,SID_utilisateur_evtx,evenement_courant_fichier_evtx.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f"),evtx_to_xml[1][3].text))

                    elif evenement_courant_fichier_evtx.get_event_identifier() == 20001 :

                        evtx_to_xml = xml.etree.ElementTree.fromstring(evenement_courant_fichier_evtx.get_xml_string())

                        if evtx_to_xml[1][0][8].text != "0x00000000" and evtx_to_xml[1][0][8].text != "0"  :
                            print ("L'installation du driver %s version %s pour l'appareil %s a échoué avec le code d'erreur %s le %s UTC " %( evtx_to_xml[1][0][0].text,evtx_to_xml[1][0][1].text,evtx_to_xml[1][0][3].text,evtx_to_xml[1][0][8].text,evenement_courant_fichier_evtx.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))
                        else:
                            print ("Le driver %s version %s pour l'appareil %s  a été correctement installé le %s UTC " %( evtx_to_xml[1][0][0].text,evtx_to_xml[1][0][1].text,evtx_to_xml[1][0][3].text,evenement_courant_fichier_evtx.get_creation_time().strftime("%d-%m-%Y %H:%M:%S.%f")))


                    i += 1 
    
            evtx_file.close()

    #Analyse Prefetch s'il est activé uniquement pour les applications (option définie à  1) ou pour application et boot (option définie à 3)

    LISTE_BINAIRE_PREFETCH_A_DUMP = ["CMD.EXE","POWERSHELL.EXE"]

    option_activation_prefetch = system_registry_hive.get_key("SYSTEM\ControlSet" + numero_control_set +"\Control\Session Manager\Memory Management\PrefetchParameters").get_value(value_name="EnablePrefetcher")
    if option_activation_prefetch == 3 or option_activation_prefetch == 1 :
    
        contenu_dossier_prefetch = partition_windows.open_dir(path="Windows/Prefetch")

        for fichier_prefetch in contenu_dossier_prefetch :
            nom_fichier_prefetch = fichier_prefetch.info.name.name.decode("utf-8")
            if ".pf" in nom_fichier_prefetch[-3:] :
                nom_executable_prefetch = nom_fichier_prefetch[:(nom_fichier_prefetch.rindex("-"))]
                #Permet de s'assurer que seuls les seuls fichiers Prefetch traités soient ceux des binaires intéressants 
                if nom_executable_prefetch in LISTE_BINAIRE_PREFETCH_A_DUMP :
                    #Dump des fichiers prefetch intéressants
                    file_entry = partition_windows.open("Windows/Prefetch/" + nom_fichier_prefetch)
                    resultat_dump_fichier_prefetch = dump_fichier(file_entry,"Windows/Prefetch/" + nom_fichier_prefetch,dossier_dump,limite_mo_dump_fichier,True)
                    if not resultat_dump_fichier_prefetch :
                        print("Le dump du fichier Prefetch %s a échoué" % nom_fichier_prefetch)
                        continue

                    #Lecture du fichier prefetch actuel pour récupérer de nombreuses informations intéressantes
                    pointeur_fichier_prefetch = open (dossier_dump / nom_fichier_prefetch,"rb")
                    if not pyscca.check_file_signature_file_object(pointeur_fichier_prefetch) :
                        print ("Le fichier Prefetch %s est incorrect" % nom_fichier_prefetch)
                        continue
                    
                    fichier_prefetch = pyscca.file() 
                    fichier_prefetch.open_file_object(pointeur_fichier_prefetch)

                    nombre_execution_programme = fichier_prefetch.get_run_count()
                    nombre_fichier_lues_par_programme =  fichier_prefetch.get_number_of_file_metrics_entries()

                    i = 0
                    liste_fichier_interessants_prefetch = []
                    while i != nombre_fichier_lues_par_programme  :
                        try :
                            verification_chemin_fichier_lu_prefetch = re.findall(r'^(?:\\VOLUME{[^}]+}\\|\\DEVICE\\HARDDISKVOLUME\d+\\)(?!WINDOWS|PROGRAM FILES|\$MFT)(.+)$',fichier_prefetch.get_file_metrics_entry(i).get_filename())
                            if len(verification_chemin_fichier_lu_prefetch) > 0 :
                                liste_fichier_interessants_prefetch.append(verification_chemin_fichier_lu_prefetch[0].replace("\\","/"))
                        except OSError :
                            pass
                        i += 1
                        
                        
                    if not liste_fichier_interessants_prefetch :
                        print ("L'outil %s a été exécuté %d fois depuis le dernier démarrage de la machine dumpée (il a été lancé la dernière fois le %s UTC), mais n'a pas communiqué avec des fichiers jugés suspects selon leur emplacement" % (nom_executable_prefetch,nombre_execution_programme,fichier_prefetch.get_last_run_time(0).strftime("%d-%m-%Y %H:%M:%S") ))

                    else :
                        print ("L'outil %s a été exécuté %d fois depuis le dernier démarrage de la machine dumpée (il a été lancé la dernière fois le %s UTC), et a communiqué avec les fichiers suivants jugés suspects selon leur emplacement:\n" % (nom_executable_prefetch,nombre_execution_programme,fichier_prefetch.get_last_run_time(0).strftime("%d-%m-%Y %H:%M:%S") ))

                        for chemin_fichier_detecte_par_analyse_prefetch in liste_fichier_interessants_prefetch :

                            try:
                                pointeur_fichier_important_prefetch = partition_windows.open(chemin_fichier_detecte_par_analyse_prefetch)     
                                os.makedirs(dossier_dump / "dump_fichier_important_prefetch" / chemin_fichier_detecte_par_analyse_prefetch[:chemin_fichier_detecte_par_analyse_prefetch.rindex("/")],exist_ok=True )
                                resultat_dump_fichier_important_prefetch = dump_fichier(pointeur_fichier_important_prefetch,chemin_fichier_detecte_par_analyse_prefetch,dossier_dump / "dump_fichier_important_prefetch" / chemin_fichier_detecte_par_analyse_prefetch[:chemin_fichier_detecte_par_analyse_prefetch.rindex("/")],limite_mo_dump_fichier,False)
                                if not resultat_dump_fichier_important_prefetch :
                                    print ("  %s : Le dump de ce fichier a échoué. Il est possible qu'il ait été supprimé ou qu'il soit stocké sur une autre partition" %  chemin_fichier_detecte_par_analyse_prefetch)
                                else:
                                    print ("  %s : Le dump de ce fichier a réussi" % chemin_fichier_detecte_par_analyse_prefetch )
                            except OSError:
                                print ("  %s : Le dump de ce fichier a échoué. Il est possible qu'il ait été supprimé ou qu'il soit stocké sur une autre partition" %  chemin_fichier_detecte_par_analyse_prefetch)


                    fichier_prefetch.close()
    else :
        print ("La génération des fichiers Prefetch applicatifs est désactivée sur cette machine au niveau du registre")

  except OSError  :
    print ("La partition actuelle n'est pas la partition système")


def main () :

  if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 5) :
      print("La version de Python que vous utilisez n'est pas compatible avec ce script. Veuillez utiliser Python 3.5 ou +")
      exit(1)

  parser = argparse.ArgumentParser(description="Script d'analyse de dump disque Windows réalisé par ElTito https://github.com/ElTito-BZH")
  parser.add_argument("fichier_dump_disque", help="Emplacement du dump disque à analyser",type=str)
  parser.add_argument("chemin_dossier_dump_des_fichiers", help="Emplacement du dossier où seront dumpés les fichiers intéressants (Registre Windows par exemple)",type=str)
  parser.add_argument("--limite_taille_dump", help="Cet argument falcutatif correspond à la limite de taille en MO des fichiers qui seront dumpés par le script (50 MO par défaut). Cela ne concerne pas certains fichiers indispensables au bon fonctionnement de ce script, notamment le registre Windows",type=int,default=50,required=False )
  parser.add_argument("--reecriture_dossier_dump",help="Cet argument falcutatif doit être utilisé si vous souhaitez réécrire le contenu du dossier mentionné dans l'option chemin_dossier_dump_des_fichiers",action='store_true',required=False)
  
  arguments = parser.parse_args()

  chemin_fichier_dump_disque    = arguments.fichier_dump_disque
  dossier_dump                  = pathlib.Path(arguments.chemin_dossier_dump_des_fichiers)
  limite_mo_dump_fichier        = arguments.limite_taille_dump

  #Vérification des arguments renseignés par l'utilisateur
  if not os.path.exists(chemin_fichier_dump_disque) :
      print ("Le fichier %s n'existe pas. Veuillez relancer ce script en saisissant le bon chemin" % chemin_fichier_dump_disque )
      exit(1)
  elif not os.access(chemin_fichier_dump_disque, os.R_OK) :
      print ("Le fichier %s n'est pas lisible par l'utilisateur courant" % chemin_fichier_dump_disque )
      exit(1)
  #Vérifie que le fichier reseigné dans l'option fichier_dump_disque est dans un format lisible par la librairie Sleuthkit
  try :
    image_file = pytsk3.Img_Info(chemin_fichier_dump_disque)
    volume = pytsk3.Volume_Info(image_file)
  except OSError :
      print ("Erreur lors de la lecture du fichier %s par la librairie Sleuthkit. Veuillez vous assurer qu'il s'agit bien d'un fichier correspondant à un disque dumpé" % chemin_fichier_dump_disque)
      exit(1)

  if os.path.exists(dossier_dump) :
      if os.path.isfile(dossier_dump) :
          print ("%s correspond à l'emplacement d'un fichier déjà existant sur votre machine. Veuillez relancer ce script et choisir un autre chemin" % dossier_dump)
          exit(1)
      if len(os.listdir(dossier_dump)) != 0 and arguments.reecriture_dossier_dump == False :
        print ("Le dossier %s existe déjà et n'est pas vide" % dossier_dump )
        exit(1)
      elif len(os.listdir(dossier_dump)) != 0 and arguments.reecriture_dossier_dump == True :
        print ("Le contenu du dossier %s sera réécrit par ce script" % dossier_dump )        
  try :
      os.mkdir(dossier_dump,0x0700)
  except FileExistsError :
      pass
  except :
      print("Erreur lors de la création du dossier %s" % dossier_dump)
      exit(1)

  numéro_partition = 1

  for part in volume:

    nom_partition = part.desc.decode('utf-8')
	#Vérifie qu'il s'agit d'une partition disque utilisée (et non d'une partition non allouée)
    if "0x" in nom_partition : 

      fs_offset = part.start * 512
      fs = pytsk3.FS_Info(image_file, offset=fs_offset)

      if "NTFS" in nom_partition or "Win95 FAT32" in nom_partition or "DOS FAT16" in nom_partition :
        print ("Début de l'analyse de la partition numéro %d" % numéro_partition)
        analyse_partition_systeme_windows(fs,limite_mo_dump_fichier,dossier_dump)

      numéro_partition +=1

if __name__ == '__main__':
    main()
