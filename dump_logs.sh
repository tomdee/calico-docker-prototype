for i in calicodockerprototype_aclmanager_1 calicodockerprototype_bird_1 calicodockerprototype_felix_1 calicodockerprototype_pluginnetwork_1 calicodockerprototype_pluginep_1; do
	sudo docker logs $i >/tmp/$i.txt 2>&1
done

FILENAME=diags-`date +%Y%m%d_%H%M%S`.tar.gz

echo "Adding files to $FILENAME"
tar -zcvf $FILENAME  /tmp/calico* config/* config/data/*

echo "Uploading file. It will be available for 14 days from the following URL"
curl -# --upload-file $FILENAME https://transfer.sh/$FILENAME

