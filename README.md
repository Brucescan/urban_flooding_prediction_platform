## 第一次打开项目

```git
复制代码到本地
git clone https://github.com/Brucescan/urban_flooding_prediction_platform.git #如果http不行就换ssh
```

```
打开命令行，进入项目根目录
cd urban_flooding_prediction_platform
```

```
因为前期后端还没写好，所以你们可以先写，不用管docker只需执行上面的就行
docker-compose up -d #后台运行
```

## 后续开发

开发完成后提交

```
git add .
git commit -m "注意这里这个参数(就是当前这个双引号里面)写中文就行，直接写你改了什么或者加了什么，只要动了项目就要写"
git push origin feature/fronted   #这里的 feature/fronted 是你们干活的分支，不要在主分支干活，等功能开发完后再往主分支上合并
```

如何合并到主分支

```
git checkout main  #切换到主分支,如果main分支不行就换master
git merge feature/fronted #将你分支的代码合并到主分支
git push origin main  #推送到github上，同理，main不行换master
```

如何更新代码

```
git pull origin main 
docker-compose down
docker-compose up -d  # 重新构建镜像
```