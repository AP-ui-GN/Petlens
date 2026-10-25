import { Ionicons } from '@expo/vector-icons';
import { Tabs, useRouter } from 'expo-router';
import { Image, Pressable, Text, View } from 'react-native';

import { useColors } from '../../src/theme-context';

function PetLensHeader() {
  const colors = useColors();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 9 }}>
      <Image
        accessibilityLabel="PetLens analysis for dogs"
        source={require('../../assets/petlens-dog-mark.png')}
        style={{ width: 34, height: 34, borderRadius: 9, backgroundColor: '#fff' }}
      />
      <View>
        <Text style={{ color: colors.text, fontSize: 16, fontWeight: '800' }}>PetLens</Text>
        <Text style={{ color: colors.muted, fontSize: 9, letterSpacing: 1.1 }}>ANALYSIS FOR DOGS</Text>
      </View>
    </View>
  );
}

export default function TabsLayout() {
  const colors = useColors();
  const router = useRouter();
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: '700' },
        headerTitle: PetLensHeader,
        headerRight: () => (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Settings"
            onPress={() => router.push('/settings')}
            hitSlop={10}
            style={{ padding: 8 }}
          >
            <Ionicons name="settings-outline" size={20} color={colors.muted} />
          </Pressable>
        ),
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
        tabBarLabelStyle: { fontSize: 9, fontWeight: '600' },
        tabBarStyle: { backgroundColor: colors.card, borderTopColor: colors.border, minHeight: 56 },
        sceneStyle: { backgroundColor: colors.background },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Overview',
          tabBarIcon: ({ color, size }) => <Ionicons name="pulse-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="analyze"
        options={{
          title: 'New analysis',
          tabBarIcon: ({ color, size }) => <Ionicons name="add-circle-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color, size }) => <Ionicons name="time-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="pet/index"
        options={{
          title: 'Pet profile',
          tabBarIcon: ({ color, size }) => <Ionicons name="paw-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="ai-use"
        options={{
          title: 'AI use',
          tabBarIcon: ({ color, size }) => <Ionicons name="shield-checkmark-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          href: null,
        }}
      />
    </Tabs>
  );
}
