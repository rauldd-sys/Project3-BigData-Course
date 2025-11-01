FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# ---- Base deps ----
RUN apt-get update && apt-get install -y \
    openjdk-8-jdk \
    wget \
    openssh-server \
    rsync \
    vim \
    sudo \
  && rm -rf /var/lib/apt/lists/*

# Ensure sshd runtime dir exists
RUN mkdir -p /var/run/sshd

# ---- Service user for Hadoop ----
RUN useradd -m -s /bin/bash hduser && \
    echo "hduser:hduser" | chpasswd && \
    usermod -aG sudo hduser

# ---- Hadoop install ----
ENV HADOOP_VERSION=3.3.6
ENV HADOOP_HOME=/opt/hadoop
ENV HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop
# Prepend Hadoop to PATH at image level
ENV PATH=/opt/hadoop/bin:/opt/hadoop/sbin:${PATH}

RUN wget -q https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz && \
    tar -xzf hadoop-${HADOOP_VERSION}.tar.gz && \
    mv hadoop-${HADOOP_VERSION} ${HADOOP_HOME} && \
    rm hadoop-${HADOOP_VERSION}.tar.gz && \
    chown -R hduser:hduser ${HADOOP_HOME}

# ---- hadoop-env.sh: set JAVA_HOME discovered at build time ----
RUN JAVA_BIN="$(readlink -f /usr/bin/java)" && \
    JAVA_HOME_RUNTIME="${JAVA_BIN%/bin/java}" && \
    printf 'export JAVA_HOME=%s\n' "$JAVA_HOME_RUNTIME" >> ${HADOOP_CONF_DIR}/hadoop-env.sh

# ---- Hadoop configs ----
# core-site.xml
RUN cat > ${HADOOP_CONF_DIR}/core-site.xml <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://localhost:9000</value>
  </property>
  <property>
    <name>hadoop.tmp.dir</name>
    <value>/tmp/hadoop-${user.name}</value>
  </property>
</configuration>
XML

# hdfs-site.xml
RUN cat > ${HADOOP_CONF_DIR}/hdfs-site.xml <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <property>
    <name>dfs.replication</name>
    <value>1</value>
  </property>
  <property>
    <name>dfs.namenode.name.dir</name>
    <value>file:///tmp/hadoop/hdfs/namenode</value>
  </property>
  <property>
    <name>dfs.datanode.data.dir</name>
    <value>file:///tmp/hadoop/hdfs/datanode</value>
  </property>
</configuration>
XML

# mapred-site.xml
RUN cat > ${HADOOP_CONF_DIR}/mapred-site.xml <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <property>
    <name>mapreduce.framework.name</name>
    <value>yarn</value>
  </property>
  <property>
    <name>mapreduce.application.classpath</name>
    <value>/opt/hadoop/share/hadoop/mapreduce/*:/opt/hadoop/share/hadoop/mapreduce/lib/*</value>
  </property>
</configuration>
XML

# yarn-site.xml
RUN cat > ${HADOOP_CONF_DIR}/yarn-site.xml <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <property>
    <name>yarn.nodemanager.aux-services</name>
    <value>mapreduce_shuffle</value>
  </property>
  <property>
    <name>yarn.nodemanager.env-whitelist</name>
    <value>JAVA_HOME,HADOOP_COMMON_HOME,HADOOP_HDFS_HOME,HADOOP_CONF_DIR,CLASSPATH_PREPEND_DISTCACHE,HADOOP_YARN_HOME,HADOOP_MAPRED_HOME,HADOOP_HOME,HADOOP_PREFIX,PATH</value>
  </property>
</configuration>
XML

# workers (single-node)
RUN printf "localhost\n" > ${HADOOP_CONF_DIR}/workers

# Let Hadoop scripts SSH without prompts
RUN printf '\nexport HADOOP_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"\n' \
  >> ${HADOOP_CONF_DIR}/hadoop-env.sh

# ---- Passwordless SSH for hduser ----
RUN su - hduser -c 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
  ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa && \
  cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys && \
  printf "Host localhost\n  StrictHostKeyChecking no\n  UserKnownHostsFile=/dev/null\n" > ~/.ssh/config && \
  chmod 600 ~/.ssh/authorized_keys ~/.ssh/config'

# ---- Pre-create HDFS storage and give it to hduser ----
RUN mkdir -p /tmp/hadoop/hdfs/namenode /tmp/hadoop/hdfs/datanode && \
    chown -R hduser:hduser /tmp/hadoop

# ---- Bootstrap (idempotent) ----
RUN cat > /etc/bootstrap.sh <<'BOOT'
#!/bin/bash
set -euo pipefail

# Start SSH server
service ssh start

# Resolve JAVA_HOME at runtime too (extra safety)
JAVA_BIN="$(readlink -f /usr/bin/java || true)"
if [ -n "${JAVA_BIN:-}" ]; then
  export JAVA_HOME="${JAVA_BIN%/bin/java}"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

export HADOOP_HOME=/opt/hadoop
export HADOOP_PREFIX=/opt/hadoop
export PATH="$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH"

# Ensure single-node workers file is present
grep -qxF "localhost" "$HADOOP_HOME/etc/hadoop/workers" || echo "localhost" >> "$HADOOP_HOME/etc/hadoop/workers"

# Ensure hduser SSH is usable (idempotent)
su - hduser -c 'mkdir -p ~/.ssh && chmod 700 ~/.ssh'
if ! su - hduser -c 'test -f ~/.ssh/id_rsa'; then
  su - hduser -c 'ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa'
fi
su - hduser -c 'touch ~/.ssh/authorized_keys ~/.ssh/config && chmod 600 ~/.ssh/authorized_keys ~/.ssh/config'
su - hduser -c 'grep -qF "$(cat ~/.ssh/id_rsa.pub)" ~/.ssh/authorized_keys || cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys'
su - hduser -c 'printf "Host localhost\n  StrictHostKeyChecking no\n  UserKnownHostsFile=/dev/null\n" > ~/.ssh/config'

# Format NN once (as hduser)
if [ ! -d "/tmp/hadoop/hdfs/namenode/current" ]; then
  echo "Formatting namenode as hduser..."
  su - hduser -c "$HADOOP_HOME/bin/hdfs namenode -format -force -nonInteractive"
fi

# Stop stale daemons/pids (idempotent)
su - hduser -c "hdfs --daemon stop namenode"          || true
su - hduser -c "hdfs --daemon stop datanode"          || true
su - hduser -c "hdfs --daemon stop secondarynamenode" || true
su - hduser -c "yarn --daemon stop resourcemanager"   || true
su - hduser -c "yarn --daemon stop nodemanager"       || true
rm -f /tmp/hadoop-hduser-*.pid

# Start via Hadoop scripts (which SSH to localhost)
su - hduser -c "start-dfs.sh"
su - hduser -c "start-yarn.sh"

echo "Hadoop services started."
BOOT
RUN chmod +x /etc/bootstrap.sh

# ---- Runtime ----
WORKDIR /workspace

# Web UIs + RPC ports often used
EXPOSE 9870 9864 8088 9000 8030 8031 8032

# Keep container alive for VS Code; postStart will run /etc/bootstrap.sh
CMD ["sleep", "infinity"]