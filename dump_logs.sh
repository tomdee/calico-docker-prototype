for i in calicodockerprototype_aclmanager_1 calicodockerprototype_bird_1 calicodockerprototype_felix_1 calicodockerprototype_pluginnetwork_1 calicodockerprototype_pluginep_1; do
sudo docker logs $i >$i.txt 2>&1
done
